"""
llm_service.py — Centralized LLM Service (Renuka Tasks 1-5).

This module is the ONLY file that touches the model. Every other file
calls generate() or extract().

  Task 1 — one file, one place: generate(), extract(), model built once.
  Task 2 — model swappable by a setting (LLM_PROVIDER), via providers.py.
  Task 3 — timeout, retry-with-backoff, circuit breaker around every call.
  Task 4 — response cache (hits/misses) and a regex fallback, clearly
           marked source="fallback", used whenever the model is in trouble.
  Task 5 — settings from config.py, request-id-tagged logs, /health, /metrics.
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Lock
from typing import Dict, List

from cache import ResponseCache
from circuit_breaker import CircuitBreaker
from config import settings
from extract_fallback import extract_with_regex
from providers import build_provider
from request_context import request_id_var
from schemas import InvoiceFields

# ---------------------------------------------------------------------
# Logging (every line is tagged with the current request id)
# ---------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)

LOG_FILE = Path("logs/llm_calls.log")

_handler = logging.FileHandler(LOG_FILE)
_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - rid=%(request_id)s - %(message)s")
)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.addFilter(_RequestIdFilter())

PROMPTS_DIR = Path("prompts")
BEST_PROMPT = "extraction_v3_worked_example.txt"


# ---------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be loaded or used. Callers only ever
    see this exception — timeouts, transient errors, and an open
    breaker all surface as LLMUnavailable."""

    pass


# ---------------------------------------------------------------------
# Provider (built once, swappable via LLM_PROVIDER)
# ---------------------------------------------------------------------

try:
    _provider = build_provider(settings.llm_provider, settings.model_name)
    logger.info("Loaded provider=%s model=%s", settings.llm_provider, settings.model_name)
except Exception as e:
    raise LLMUnavailable(
        f"Unable to build provider '{settings.llm_provider}' "
        f"(model '{settings.model_name}'): {e}"
    )

_executor = ThreadPoolExecutor(max_workers=2)
_breaker = CircuitBreaker(
    failure_threshold=settings.breaker_threshold,
    cooldown_s=settings.breaker_cool_off_s,
)
_cache = ResponseCache()

_metrics_lock = Lock()
_metrics_state = {
    "requests": 0,
    "total_latency_ms": 0.0,
    "last_latency_ms": 0,
    "fallback_count": 0,
    "answer_count": 0,
}


def _record_latency(latency_ms: float) -> None:
    with _metrics_lock:
        _metrics_state["requests"] += 1
        _metrics_state["total_latency_ms"] += latency_ms
        _metrics_state["last_latency_ms"] = round(latency_ms, 2)


def _record_answer(used_fallback: bool) -> None:
    with _metrics_lock:
        _metrics_state["answer_count"] += 1
        if used_fallback:
            _metrics_state["fallback_count"] += 1


# ---------------------------------------------------------------------
# Resilience: timeout -> retry with backoff -> circuit breaker
# ---------------------------------------------------------------------


def _call_provider_with_timeout(
    messages: List[Dict[str, str]], max_tokens: int, temperature: float
) -> str:
    future = _executor.submit(_provider.complete, messages, max_tokens, temperature)
    try:
        return future.result(timeout=settings.request_timeout_s)
    except FutureTimeoutError:
        raise LLMUnavailable(
            f"Model call timed out after {settings.request_timeout_s}s"
        )


def _call_with_resilience(
    messages: List[Dict[str, str]], max_tokens: int, temperature: float = 0.0
) -> str:
    """Timeout on every call, retry with growing backoff on transient
    errors, and a circuit breaker that stops calling the model after
    repeated failures. Never retries on a breaker-open short-circuit."""

    if not _breaker.allow_call():
        logger.warning("Breaker OPEN — short-circuiting to fallback")
        raise LLMUnavailable("Circuit breaker is open; model calls are paused.")

    backoffs = [0.5, 1.0, 2.0][: settings.max_retries]
    last_error: Exception = LLMUnavailable("no attempts made")

    for attempt, wait in enumerate([0.0] + backoffs):
        if wait:
            time.sleep(wait)
        try:
            start = time.time()
            result = _call_provider_with_timeout(messages, max_tokens, temperature)
            _record_latency((time.time() - start) * 1000)
            _breaker.record_success()
            return result
        except Exception as e:
            last_error = e
            logger.warning("Model call attempt %d failed: %s", attempt + 1, e)

    _breaker.record_failure()
    raise LLMUnavailable(str(last_error))


# ---------------------------------------------------------------------
# Text generation (cached, resilient)
# ---------------------------------------------------------------------


def generate(messages: List[Dict[str, str]], max_tokens: int = 256) -> str:
    """Generate text from the active provider. Cached; falls through
    timeout/retry/breaker protection. Raises LLMUnavailable on failure —
    callers that need a fallback (like extract()) catch it."""

    key = _cache.make_key(settings.llm_provider, str(messages), max_tokens, 0.0)
    cached = _cache.get(key)
    if cached is not None:
        logger.info("cache=hit provider=%s", settings.llm_provider)
        return cached

    result = _call_with_resilience(messages, max_tokens, temperature=0.0)
    _cache.set(key, result)
    logger.info("cache=miss provider=%s", settings.llm_provider)
    return result


def load_prompt(prompt_file: str) -> str:
    """Load a prompt template."""
    return (PROMPTS_DIR / prompt_file).read_text(encoding="utf-8")


def clean_json_response(response: str) -> str:
    """Remove markdown code fences."""
    response = response.strip()

    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]

    if response.endswith("```"):
        response = response[:-3]

    return response.strip()


def call_llm(prompt: str, max_tokens: int = 512) -> str:
    """Call generate() and clean the response."""
    messages = [{"role": "user", "content": prompt}]
    response = generate(messages=messages, max_tokens=max_tokens)
    return clean_json_response(response)


def log_result(filename: str, method: str) -> None:
    """Log extraction method (llm / retry / fallback) per file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"rid={request_id_var.get()} {filename} -> {method}\n")


# ---------------------------------------------------------------------
# Extraction: LLM -> retry -> regex fallback (Renuka Task 4)
# ---------------------------------------------------------------------


def _coerce_invoice_fields(obj) -> InvoiceFields:
    """Normalize whatever extract_with_regex()/model_validate_json()
    hands back (a pydantic model or a dict) into InvoiceFields."""
    if isinstance(obj, InvoiceFields):
        return obj
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, dict):
        data = obj
    else:
        data = {
            "vendor": getattr(obj, "vendor", ""),
            "invoice_number": getattr(obj, "invoice_number", ""),
            "invoice_date": getattr(obj, "invoice_date", ""),
            "total_amount": getattr(obj, "total_amount", 0.0),
            "currency": getattr(obj, "currency", ""),
            "line_items": getattr(obj, "line_items", []),
        }
    known_fields = InvoiceFields.model_fields.keys()
    return InvoiceFields(**{k: v for k, v in data.items() if k in known_fields})


def extract(
    invoice_text: str,
    filename: str = "sample",
    prompt_file: str = BEST_PROMPT,
) -> InvoiceFields:
    """
    Extract structured invoice data using:
      1. LLM
      2. Retry once (with the validation error appended to the prompt)
      3. Regex fallback — used whenever the breaker is open, a call
         times out, or the model returns unusable output.
    """

    prompt = load_prompt(prompt_file).replace("{text}", invoice_text)

    first_error = None

    # ---------- First attempt ----------
    try:
        response = call_llm(prompt)
        invoice = _coerce_invoice_fields(InvoiceFields.model_validate_json(response))
        invoice.source = "llm"
        confidence, needs_review = compute_extraction_confidence(invoice_text, invoice)
        invoice.confidence, invoice.needs_review = confidence, needs_review
        log_result(filename, "llm")
        _record_answer(used_fallback=False)
        return invoice
    except Exception as first_error:
        logger.warning("%s: LLM extraction failed: %s", filename, first_error)

    # ---------- Retry ----------
    try:
        error_detail = str(first_error) if first_error else "Unknown error"
        retry_prompt = (
            prompt
            + "\n\nPrevious response failed validation.\n"
            + error_detail
            + "\nReturn ONLY valid JSON."
        )
        response = call_llm(retry_prompt)
        invoice = _coerce_invoice_fields(InvoiceFields.model_validate_json(response))
        invoice.source = "llm"
        confidence, needs_review = compute_extraction_confidence(invoice_text, invoice)
        invoice.confidence, invoice.needs_review = confidence, needs_review
        log_result(filename, "retry")
        _record_answer(used_fallback=False)
        return invoice
    except Exception as retry_error:
        logger.warning("%s: Retry failed: %s", filename, retry_error)

    # ---------- Regex fallback ----------
    invoice = _coerce_invoice_fields(extract_with_regex(invoice_text))
    invoice.source = "fallback"
    invoice.confidence = 0.0
    invoice.needs_review = True
    log_result(filename, "fallback")
    _record_answer(used_fallback=True)
    return invoice


def compute_extraction_confidence(
    invoice_text: str, llm_invoice: InvoiceFields
) -> tuple[float, bool]:
    """
    Confidence signals:
      - Regex agreement: compare LLM total_amount with the regex total
      - Field completeness: whether key fields are non-empty
    Returns (confidence, needs_review).
    """
    try:
        regex_invoice = _coerce_invoice_fields(extract_with_regex(invoice_text))
        regex_total = regex_invoice.total_amount
        llm_total = llm_invoice.total_amount
        agreement = (
            1.0 if regex_total and llm_total and abs(regex_total - llm_total) < 0.01 else 0.0
        )
    except Exception:
        agreement = 0.0

    fields = [
        llm_invoice.vendor,
        llm_invoice.invoice_number,
        llm_invoice.invoice_date,
        llm_invoice.currency,
    ]
    present = sum(1 for f in fields if f and str(f).strip())
    completeness = present / len(fields) if fields else 0.0

    confidence = 0.6 * agreement + 0.4 * completeness
    needs_review = confidence < settings.confidence_threshold

    return round(confidence, 4), needs_review


# ---------------------------------------------------------------------
# Health (Renuka Task 5)
# ---------------------------------------------------------------------


def get_health():
    return {
        "status": "healthy",
        "model_loaded": True,
        "provider": settings.llm_provider,
        "model": settings.model_name,
        "breaker": _breaker.state,
        "last_latency_ms": 0,
    }


# ---------------------------------------------------------------------
# Metrics (Renuka Task 5)
# ---------------------------------------------------------------------


def get_metrics() -> dict:
    """Running totals: request count, average latency, cache hit rate,
    and fallback rate."""
    requests = _metrics_state["requests"]
    avg_latency = round(_metrics_state["total_latency_ms"] / requests, 2) if requests else 0.0
    answers = _metrics_state["answer_count"]
    fallback_rate = (
        round(_metrics_state["fallback_count"] / answers, 4) if answers else 0.0
    )
    return {
        "requests": requests,
        "avg_latency_ms": avg_latency,
        "cache_hit_rate": _cache.hit_rate,
        "fallback_rate": fallback_rate,
    }

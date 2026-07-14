"""
<<<<<<< HEAD
Week 4 – Centralized LLM Service

This module is the ONLY place that loads or talks to the LLM.
"""

from pathlib import Path

from pydantic import ValidationError

from models import Invoice
from extract_fallback import extract_with_regex

import logging
import os
import time
from typing import Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
=======
llm_service.py — The ONLY file in the project that imports transformers.

Implements all Renuka Week 4 tasks:

  Task 1 — Single model gateway
    generate(messages, max_tokens, temperature) -> str
    extract(text) -> InvoiceFields

  Task 2 — Provider pattern
    Provider Protocol  : uniform interface, swappable with one setting
    LocalQwenProvider  : Qwen2.5-0.5B-Instruct (free, CPU/GPU, no key)
    StubProvider       : canned text — tests run offline in seconds
    TinyLlamaProvider  : TinyLlama-1.1B-Chat (optional, free)

  Task 3 — Resilience
    Timeout            : every call gets REQUEST_TIMEOUT_S seconds
    Retry with backoff : 0.5 s, 1 s, 2 s on transient errors
    CircuitBreaker     : CLOSED → OPEN (cool-off) → HALF_OPEN → CLOSED

  Task 4 — Cache + fallback
    LRUCache           : keyed on (provider, prompt, max_tokens, temperature)
    Fallback           : source="fallback" when model is unavailable or broken
    Counters           : hits, misses, fallback_count — fed to /metrics

Public re-exports for backward compatibility with llm.py shim::

    from llm_service import LLMUnavailable, generate, extract

Importing this module twice does NOT reload the model (singleton pattern).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import ValidationError

from config import settings
from models import Invoice
from extract_fallback import extract_with_regex

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
>>>>>>> 4583ed1 (Complete Renuka Week 4 Tasks 1-5)

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/llm_calls.log",
<<<<<<< HEAD
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path("prompts")
LOG_FILE = Path("logs/llm_calls.log")

BEST_PROMPT = "extraction_v3_worked_example.txt"
# ---------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be loaded or used."""
    pass


# ---------------------------------------------------------------------
# Model (loaded once)
# ---------------------------------------------------------------------

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

try:

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",
        device_map="auto",
    )

    logger.info("Loaded model: %s", MODEL_NAME)

except Exception as e:
    raise LLMUnavailable(f"Unable to load model '{MODEL_NAME}': {e}")


# ---------------------------------------------------------------------
# Text Generation
# ---------------------------------------------------------------------
=======
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class LLMUnavailable(Exception):
    """
    Raised when the LLM cannot serve a request.

    Callers never see the internal error — they only see this exception,
    which tells them to use the fallback or surface an appropriate HTTP error.
    """


# ---------------------------------------------------------------------------
# Provider Protocol (Task 2)
# ---------------------------------------------------------------------------


@runtime_checkable
class Provider(Protocol):
    """
    Common interface that every provider must implement.

    Parameters are identical across all providers so the caller never changes
    when the active provider changes.
    """

    name: str

    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """
        Generate a response.

        Parameters
        ----------
        messages:
            Chat turns, e.g. [{"role": "user", "content": "..."}].
        max_tokens:
            Maximum new tokens to produce.
        temperature:
            Sampling temperature (0 = greedy / deterministic).

        Returns
        -------
        str
            Generated text only (prompt stripped).

        Raises
        ------
        LLMUnavailable
            On any model error.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# StubProvider — tests, no model required (Task 2)
# ---------------------------------------------------------------------------


class StubProvider:
    """
    Returns fixed canned text without loading any model.

    Accepts and ignores max_tokens and temperature so it is a drop-in
    replacement for any real provider.  Tests that need specific output
    can pass a custom ``response`` string.
    """

    name: str = "stub"

    _DEFAULT = (
        '{"invoice_number": "INV-STUB-001", "vendor": "Stub Corp", '
        '"invoice_date": "2024-01-01", "total_amount": 100.0, '
        '"currency": "USD", "line_items": []}'
    )

    def __init__(self, response: Optional[str] = None) -> None:
        self._response = response if response is not None else self._DEFAULT

    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """Return canned text immediately (no model, no network)."""
        return self._response


# ---------------------------------------------------------------------------
# LocalQwenProvider — Qwen2.5-0.5B-Instruct (Task 2)
# ---------------------------------------------------------------------------


class LocalQwenProvider:
    """
    Wraps Qwen/Qwen2.5-0.5B-Instruct via Hugging Face transformers.

    ``import transformers`` and ``import torch`` live ONLY inside __init__
    so that importing llm_service with LLM_PROVIDER=stub never touches the
    GPU or the model cache.
    """

    name: str = "local"

    def __init__(self, model_name: str = settings.model_name) -> None:
        try:
            import torch  # noqa: PLC0415
            from transformers import (  # noqa: PLC0415
                AutoModelForCausalLM,
                AutoTokenizer,
            )

            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = AutoModelForCausalLM.from_pretrained(
                model_name,
                trust_remote_code=True,
            ).to(device)
            logger.info("LocalQwenProvider: loaded '%s' on %s", model_name, device)
        except Exception as exc:
            raise LLMUnavailable(
                f"Cannot load Qwen model '{model_name}': {exc}"
            ) from exc

    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """Run the Qwen model synchronously and return generated text."""
        try:
            text = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self._tokenizer(text, return_tensors="pt").to(
                self._model.device
            )
            input_len = inputs.input_ids.shape[-1]
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if temperature > 0 else None,
                do_sample=temperature > 0,
            )
            generated = outputs[0][input_len:]
            return self._tokenizer.decode(
                generated, skip_special_tokens=True
            ).strip()
        except Exception as exc:
            logger.error("LocalQwenProvider.complete failed: %s", exc)
            raise LLMUnavailable(f"Qwen generation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# TinyLlamaProvider — TinyLlama-1.1B-Chat (optional, Task 2)
# ---------------------------------------------------------------------------


class TinyLlamaProvider:
    """
    Wraps TinyLlama/TinyLlama-1.1B-Chat-v1.0 via Hugging Face pipeline.

    Free, open-weight, runs on CPU.  Enable with LLM_PROVIDER=tinyllama.
    """

    name: str = "tinyllama"

    def __init__(self, model_name: str = settings.tinyllama_model_name) -> None:
        try:
            from transformers import pipeline  # noqa: PLC0415

            self._pipe = pipeline(
                "text-generation",
                model=model_name,
                torch_dtype="auto",
                device_map="auto",
            )
            logger.info("TinyLlamaProvider: loaded '%s'", model_name)
        except Exception as exc:
            raise LLMUnavailable(
                f"Cannot load TinyLlama model '{model_name}': {exc}"
            ) from exc

    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """Run TinyLlama and strip the prompt prefix from the output."""
        try:
            prompt = "\n".join(
                f"{m['role'].upper()}: {m['content']}" for m in messages
            )
            out = self._pipe(
                prompt,
                max_new_tokens=max_tokens,
                do_sample=temperature > 0,
                temperature=temperature if temperature > 0 else 1.0,
            )
            full: str = out[0]["generated_text"]
            return full[len(prompt):].strip()
        except Exception as exc:
            logger.error("TinyLlamaProvider.complete failed: %s", exc)
            raise LLMUnavailable(f"TinyLlama generation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Circuit Breaker (Task 3)
# ---------------------------------------------------------------------------


class BreakerState(str, Enum):
    """States as described in Martin Fowler's Circuit Breaker pattern."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Thread-safe circuit breaker with three states.

    State machine::

        CLOSED ---(threshold failures)---> OPEN
        OPEN   ---(cool_off_s elapsed)---> HALF_OPEN
        HALF_OPEN ---(success)-----------> CLOSED
        HALF_OPEN ---(failure)-----------> OPEN
    """

    def __init__(self, threshold: int, cool_off_s: float) -> None:
        self._threshold = threshold
        self._cool_off_s = cool_off_s
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = threading.RLock()

    @property
    def state(self) -> BreakerState:
        """Return current state; auto-transition OPEN → HALF_OPEN if cooled."""
        with self._lock:
            if (
                self._state == BreakerState.OPEN
                and time.monotonic() - self._opened_at >= self._cool_off_s
            ):
                self._state = BreakerState.HALF_OPEN
                logger.info("CircuitBreaker: OPEN → HALF_OPEN (probe allowed)")
            return self._state

    def allow_request(self) -> bool:
        """Return True when a call to the provider should be attempted."""
        return self.state in (BreakerState.CLOSED, BreakerState.HALF_OPEN)

    def record_success(self) -> None:
        """Reset failure counter and close the breaker."""
        with self._lock:
            prev = self._state
            self._failure_count = 0
            self._state = BreakerState.CLOSED
            if prev != BreakerState.CLOSED:
                logger.info("CircuitBreaker: → CLOSED (success)")

    def record_failure(self) -> None:
        """Increment counter; open when threshold is reached or probe fails."""
        with self._lock:
            self._failure_count += 1
            if (
                self._failure_count >= self._threshold
                or self._state == BreakerState.HALF_OPEN
            ):
                self._state = BreakerState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "CircuitBreaker: → OPEN after %d failure(s)",
                    self._failure_count,
                )


# ---------------------------------------------------------------------------
# LRU Cache (Task 4)
# ---------------------------------------------------------------------------


class LRUCache:
    """
    Thread-safe LRU cache for LLM responses.

    Cache key = SHA-256 of (provider_name, messages, max_tokens, temperature).
    Exposes ``hits`` and ``misses`` counters consumed by ``get_metrics()``.
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._store: OrderedDict[str, str] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0

    @staticmethod
    def make_key(
        provider_name: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Build a deterministic, collision-resistant cache key."""
        raw = json.dumps(
            {"p": provider_name, "m": messages, "t": max_tokens, "temp": temperature},
            sort_keys=True,
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> Optional[str]:
        """Return the cached value, or None on a miss (updates counters)."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self.hits += 1
                return self._store[key]
            self.misses += 1
            return None

    def put(self, key: str, value: str) -> None:
        """Store a value; evict the oldest entry when at capacity."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            else:
                if len(self._store) >= self._maxsize:
                    self._store.popitem(last=False)
            self._store[key] = value


# ---------------------------------------------------------------------------
# Module-level singletons — built exactly once on first import
# ---------------------------------------------------------------------------


def _build_provider() -> Any:
    """Instantiate the provider selected by settings.llm_provider."""
    name = settings.llm_provider.lower().strip()
    logger.info("Building LLM provider: '%s'", name)
    if name == "stub":
        return StubProvider()
    if name == "tinyllama":
        return TinyLlamaProvider()
    return LocalQwenProvider()


_provider: Any = _build_provider()

_breaker: CircuitBreaker = CircuitBreaker(
    threshold=settings.breaker_threshold,
    cool_off_s=settings.breaker_cool_off_s,
)

_cache: LRUCache = LRUCache(maxsize=settings.cache_max_size)

# One background thread pool for blocking model calls (keeps FastAPI async)
_executor: concurrent.futures.ThreadPoolExecutor = (
    concurrent.futures.ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="llm_worker"
    )
)

# ---------------------------------------------------------------------------
# Metrics counters — thread-safe, read by get_metrics()
# ---------------------------------------------------------------------------

_metrics_lock = threading.Lock()
_total_calls: int = 0
_total_latency_ms: float = 0.0
_fallback_count: int = 0
_last_latency_ms: float = 0.0


def get_metrics() -> Dict[str, Any]:
    """Return a live snapshot of service performance metrics."""
    with _metrics_lock:
        total = max(_total_calls, 1)  # avoid ZeroDivisionError
        cache_total = max(_cache.hits + _cache.misses, 1)
        return {
            "requests": _total_calls,
            "avg_latency_ms": round(_total_latency_ms / total, 1),
            "cache_hit_rate": round(_cache.hits / cache_total, 4),
            "fallback_rate": round(_fallback_count / total, 4),
        }


def get_health() -> Dict[str, Any]:
    """Return current health status of the LLM service."""
    return {
        "model_loaded": not isinstance(_provider, StubProvider),
        "provider": _provider.name,
        "breaker": _breaker.state.value,
        "last_latency_ms": _last_latency_ms,
    }


# ---------------------------------------------------------------------------
# Backoff schedule (Task 3)
# ---------------------------------------------------------------------------

_BACKOFF_S = [0.5, 1.0, 2.0]


# ---------------------------------------------------------------------------
# Public API — generate() (Tasks 1, 3, 4)
# ---------------------------------------------------------------------------
>>>>>>> 4583ed1 (Complete Renuka Week 4 Tasks 1-5)


def generate(
    messages: List[Dict[str, str]],
    max_tokens: int = 256,
<<<<<<< HEAD
) -> str:
    """
    Generate text from the LLM.
    """

    try:

        start = time.time()

        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = tokenizer(
            prompt,
            return_tensors="pt",
        ).to(model.device)

        input_tokens = inputs.input_ids.shape[-1]

        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            temperature=0,
        )

        generated = outputs[0][input_tokens:]

        answer = tokenizer.decode(
            generated,
            skip_special_tokens=True,
        ).strip()

        logger.info(
            "Latency=%.2fs Input=%d Output=%d",
            time.time() - start,
            input_tokens,
            len(generated),
        )

        return answer

    except Exception as e:
        logger.exception("Generation failed")
        raise LLMUnavailable(str(e))
    
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

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    response = generate(
        messages=messages,
        max_tokens=max_tokens,
    )

    return clean_json_response(response)


def log_result(filename: str, method: str) -> None:
    """Log extraction method."""

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{filename} -> {method}\n")
    



def extract(
    invoice_text: str,
    filename: str = "sample",
    prompt_file: str = BEST_PROMPT,
) -> Invoice:
    """
    Extract structured invoice data using:
    1. LLM
    2. Retry once on validation failure
    3. Regex fallback
    """

    prompt = load_prompt(prompt_file).replace("{text}", invoice_text)

    # ---------- First Attempt ----------
    try:

        response = call_llm(prompt)

        invoice = Invoice.model_validate_json(response)

        log_result(filename, "llm")

        return invoice

    except (ValidationError, Exception) as first_error:

        logger.warning(
            "%s: LLM extraction failed: %s",
            filename,
            first_error,
        )

    # ---------- Retry ----------
    try:

        retry_prompt = (
            prompt
            + "\n\nPrevious response failed validation.\n"
            + str(first_error)
            + "\nReturn ONLY valid JSON."
        )

        response = call_llm(retry_prompt)

        invoice = Invoice.model_validate_json(response)

        log_result(filename, "retry")

        return invoice

    except Exception as retry_error:

        logger.warning(
            "%s: Retry failed: %s",
            filename,
            retry_error,
        )

    # ---------- Regex ----------
    invoice = extract_with_regex(invoice_text)

    log_result(filename, "fallback")

    return invoice
=======
    temperature: float = 0.0,
) -> str:
    """
    Generate a response via the active provider.

    Safety net applied in order:
    1. Cache check — return stored result immediately on a hit.
    2. Circuit breaker — raise LLMUnavailable instantly when OPEN.
    3. Timeout — abort after ``REQUEST_TIMEOUT_S`` seconds.
    4. Retry with backoff — up to ``MAX_RETRIES`` attempts (0.5 s / 1 s / 2 s).
    5. On all retries exhausted — open the breaker and raise LLMUnavailable.

    Parameters
    ----------
    messages:
        Chat messages, e.g. [{"role": "user", "content": "..."}].
    max_tokens:
        Maximum new tokens to generate.
    temperature:
        Sampling temperature (0 = greedy/deterministic).

    Returns
    -------
    str
        The generated text.

    Raises
    ------
    LLMUnavailable
        When the circuit is open or all retries are exhausted.
    """
    global _total_calls, _total_latency_ms, _last_latency_ms  # noqa: PLW0603

    # 1 — Cache check
    cache_key = LRUCache.make_key(_provider.name, messages, max_tokens, temperature)
    cached = _cache.get(cache_key)
    if cached is not None:
        logger.info("generate: cache=HIT provider=%s", _provider.name)
        return cached

    # 2 — Circuit breaker check
    if not _breaker.allow_request():
        raise LLMUnavailable(
            f"Circuit breaker OPEN for provider '{_provider.name}'; "
            "retry after cool-off period."
        )

    t_start = time.monotonic()
    last_exc: Exception = LLMUnavailable("No attempts made")
    retries = min(settings.max_retries, len(_BACKOFF_S))

    for attempt in range(retries):
        try:
            # 3 — Submit to thread pool with timeout
            future = _executor.submit(
                _provider.complete, messages, max_tokens, temperature
            )
            result: str = future.result(timeout=settings.request_timeout_s)

            # ── Success path ──
            latency_ms = (time.monotonic() - t_start) * 1000.0
            with _metrics_lock:
                _total_calls += 1
                _total_latency_ms += latency_ms
                _last_latency_ms = latency_ms

            _breaker.record_success()
            _cache.put(cache_key, result)

            logger.info(
                "generate: cache=MISS provider=%s latency_ms=%.0f attempt=%d",
                _provider.name,
                latency_ms,
                attempt + 1,
            )
            return result

        except concurrent.futures.TimeoutError:
            last_exc = LLMUnavailable(
                f"Provider timed out after {settings.request_timeout_s}s "
                f"(attempt {attempt + 1})"
            )
            logger.warning(
                "generate: TIMEOUT attempt=%d provider=%s",
                attempt + 1,
                _provider.name,
            )
            _breaker.record_failure()

        except LLMUnavailable as exc:
            last_exc = exc
            logger.warning(
                "generate: LLMUnavailable attempt=%d: %s", attempt + 1, exc
            )
            _breaker.record_failure()

        except Exception as exc:
            last_exc = LLMUnavailable(f"Unexpected provider error: {exc}")
            logger.error(
                "generate: unexpected error attempt=%d: %s", attempt + 1, exc
            )
            _breaker.record_failure()

        # 4 — Wait before next attempt (except after the last one)
        if attempt < retries - 1:
            time.sleep(_BACKOFF_S[attempt])

    # 5 — All retries exhausted
    raise last_exc


# ---------------------------------------------------------------------------
# Extraction helpers (Task 1 / 4)
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path("prompts")
_BEST_PROMPT_FILE = "extraction_v3_worked_example.txt"
_REQUIRED_FIELDS = ("invoice_number", "vendor", "invoice_date", "total_amount")


def _load_extraction_prompt() -> str:
    """Read the best extraction prompt from disk."""
    return (_PROMPTS_DIR / _BEST_PROMPT_FILE).read_text(encoding="utf-8")


def _clean_json(text: str) -> str:
    """Strip markdown code fences from LLM JSON output."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _fields_parsed_ratio(inv: Invoice) -> float:
    """Fraction of required fields that are non-empty / non-zero."""
    parsed = sum(
        1
        for f in _REQUIRED_FIELDS
        if str(getattr(inv, f, "") or "").strip() not in ("", "0", "0.0")
    )
    return parsed / len(_REQUIRED_FIELDS)


def _agreement_score(llm_inv: Invoice, regex_inv: Invoice) -> float:
    """
    Pairwise field-level agreement between LLM and regex results.

    Returns a value in [0.0, 1.0].
    """
    checks = agreements = 0

    if llm_inv.vendor and regex_inv.vendor:
        checks += 1
        lv = llm_inv.vendor.upper().strip()
        rv = regex_inv.vendor.upper().strip()
        if lv == rv or lv in rv or rv in lv:
            agreements += 1

    checks += 1
    if abs(llm_inv.total_amount - regex_inv.total_amount) < 1.0:
        agreements += 1

    if llm_inv.currency and regex_inv.currency:
        checks += 1
        if llm_inv.currency.upper() == regex_inv.currency.upper():
            agreements += 1

    if llm_inv.invoice_number and regex_inv.invoice_number:
        checks += 1
        li = llm_inv.invoice_number.strip()
        ri = regex_inv.invoice_number.strip()
        if li == ri or li in ri or ri in li:
            agreements += 1

    return agreements / checks if checks > 0 else 0.0


def _compute_confidence(llm_inv: Optional[Invoice], regex_inv: Invoice) -> float:
    """
    Combine LLM/regex agreement and field-parsed ratio into one score.

    Formula: 0.5 * agreement + 0.5 * fields_parsed
    Falls back to 0.3 * fields_parsed when LLM failed entirely.
    """
    if llm_inv is None:
        return round(0.3 * _fields_parsed_ratio(regex_inv), 4)
    agreement = _agreement_score(llm_inv, regex_inv)
    fields = _fields_parsed_ratio(llm_inv)
    return round(0.5 * agreement + 0.5 * fields, 4)


def _to_invoice_fields(
    inv: Invoice,
    source: str,
    confidence: float,
    needs_review: bool,
) -> "InvoiceFields":  # forward ref resolved at call time
    """Convert an Invoice + metadata to the public InvoiceFields schema."""
    from schemas import InvoiceFields  # local import avoids circular dependency

    return InvoiceFields(
        invoice_number=inv.invoice_number,
        vendor=inv.vendor,
        invoice_date=inv.invoice_date,
        total_amount=inv.total_amount,
        currency=inv.currency,
        line_items=[item.model_dump() for item in inv.line_items],
        source=source,
        confidence=confidence,
        needs_review=needs_review,
    )


# ---------------------------------------------------------------------------
# Public API — extract() (Tasks 1, 4)
# ---------------------------------------------------------------------------


def extract(text: str) -> "InvoiceFields":
    """
    Extract structured invoice fields from raw invoice text.

    Pipeline
    --------
    1. Always run the regex extractor (needed for agreement scoring).
    2. Call generate() with the best extraction prompt.
    3. Validate the JSON response into an Invoice.
    4. Retry once if validation fails (error is appended to the prompt).
    5. If both attempts fail, use the regex result as the fallback.
    6. Compute confidence from LLM/regex agreement + field coverage.
    7. Set source="llm" or source="fallback".
    8. Mark needs_review=True when confidence < CONFIDENCE_THRESHOLD.

    Parameters
    ----------
    text:
        Raw text extracted from a PDF invoice.

    Returns
    -------
    InvoiceFields
        Invoice fields plus metadata (source, confidence, needs_review).
    """
    global _fallback_count  # noqa: PLW0603

    # Always extract with regex for comparison / fallback
    regex_inv = extract_with_regex(text)

    def _use_fallback(llm_inv: Optional[Invoice] = None) -> "InvoiceFields":
        global _fallback_count  # noqa: PLW0603
        with _metrics_lock:
            _fallback_count += 1
        confidence = _compute_confidence(llm_inv, regex_inv)
        needs_review = confidence < settings.confidence_threshold
        logger.info(
            "extract: source=fallback confidence=%.2f needs_review=%s",
            confidence,
            needs_review,
        )
        return _to_invoice_fields(regex_inv, "fallback", confidence, needs_review)

    # Empty input → fallback immediately
    if not text or not text.strip():
        return _use_fallback()

    # Build prompt
    try:
        prompt_template = _load_extraction_prompt()
    except OSError:
        logger.warning("extract: prompt file not found, using fallback")
        return _use_fallback()

    prompt = prompt_template.replace("{text}", text)
    messages = [{"role": "user", "content": prompt}]

    # Stage 1 — LLM attempt
    llm_inv: Optional[Invoice] = None
    first_error: Optional[Exception] = None

    try:
        raw = generate(messages, max_tokens=512)
        llm_inv = Invoice.model_validate_json(_clean_json(raw))
    except LLMUnavailable:
        # Breaker is open or all retries failed → skip retry, go straight to fallback
        return _use_fallback()
    except (ValidationError, Exception) as exc:
        first_error = exc
        logger.warning("extract: stage1 validation failed: %s", exc)

    # Stage 2 — Retry once with error context appended
    if llm_inv is None and first_error is not None:
        retry_messages = [
            {
                "role": "user",
                "content": (
                    prompt
                    + "\n\nPrevious response failed validation:\n"
                    + str(first_error)
                    + "\nReturn ONLY valid JSON matching the schema exactly."
                ),
            }
        ]
        try:
            raw = generate(retry_messages, max_tokens=512)
            llm_inv = Invoice.model_validate_json(_clean_json(raw))
        except LLMUnavailable:
            return _use_fallback()
        except Exception as exc:
            logger.warning("extract: stage2 retry failed: %s", exc)
            llm_inv = None

    # Stage 3 — Regex fallback if both attempts failed
    if llm_inv is None:
        return _use_fallback()

    # LLM succeeded — compute confidence and return
    confidence = _compute_confidence(llm_inv, regex_inv)
    needs_review = confidence < settings.confidence_threshold
    logger.info(
        "extract: source=llm provider=%s confidence=%.2f needs_review=%s",
        _provider.name,
        confidence,
        needs_review,
    )
    return _to_invoice_fields(llm_inv, "llm", confidence, needs_review)


# ---------------------------------------------------------------------------
# Public symbols
# ---------------------------------------------------------------------------

__all__ = [
    "LLMUnavailable",
    "Provider",
    "StubProvider",
    "LocalQwenProvider",
    "TinyLlamaProvider",
    "BreakerState",
    "CircuitBreaker",
    "LRUCache",
    "generate",
    "extract",
    "get_metrics",
    "get_health",
]
>>>>>>> 4583ed1 (Complete Renuka Week 4 Tasks 1-5)

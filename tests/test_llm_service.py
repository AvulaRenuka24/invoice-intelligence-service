# tests/test_llm_service.py
#
# Renuka's half: llm_service.py (generate/extract, retry, fallback,
# cache, circuit breaker). Mocks the provider the Week 3 way so no
# test downloads or calls the real model — everything runs offline
# in seconds.

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import llm_service
from llm_service import extract, generate, LLMUnavailable
from schemas import InvoiceFields


SAMPLE_INVOICE_TEXT = (
    "Vendor: Acme Supplies\n"
    "Invoice Number: INV-24990\n"
    "Invoice Date: 2026-03-01\n"
    "Total: 13082.48 USD\n"
)

VALID_LLM_JSON = (
    '{"vendor": "Acme Supplies", "invoice_number": "INV-24990", '
    '"invoice_date": "2026-03-01", "total_amount": 13082.48, '
    '"currency": "USD", "line_items": []}'
)


def test_extract_happy_path(monkeypatch):
    monkeypatch.setattr(llm_service, "call_llm", lambda prompt, max_tokens=512: VALID_LLM_JSON)
    result = extract(SAMPLE_INVOICE_TEXT, filename="sample.pdf")
    assert isinstance(result, InvoiceFields)
    assert result.source == "llm"
    assert result.vendor == "Acme Supplies"
    assert result.total_amount == 13082.48
    assert result.needs_review in (True, False)


def test_extract_falls_back_when_model_unavailable(monkeypatch):
    def boom(prompt, max_tokens=512):
        raise LLMUnavailable("model timed out")
    monkeypatch.setattr(llm_service, "call_llm", boom)
    result = extract(SAMPLE_INVOICE_TEXT, filename="sample.pdf")
    assert result.source == "fallback"
    assert result.needs_review is True
    assert result.confidence == 0.0


def test_extract_handles_junk_input_without_crashing(monkeypatch):
    monkeypatch.setattr(
        llm_service, "call_llm", lambda prompt, max_tokens=512: "not json at all !!"
    )
    result = extract("", filename="garbled.pdf")
    assert isinstance(result, InvoiceFields)
    assert result.source == "fallback"
    assert result.needs_review is True


def test_generate_uses_cache_on_repeat_call(monkeypatch):
    calls = {"count": 0}

    def fake_resilient_call(messages, max_tokens, temperature=0.0):
        calls["count"] += 1
        return "cached response"

    monkeypatch.setattr(llm_service, "_call_with_resilience", fake_resilient_call)
    messages = [{"role": "user", "content": "same prompt every time"}]
    first = generate(messages, max_tokens=32)
    second = generate(messages, max_tokens=32)
    assert first == second == "cached response"
    assert calls["count"] == 1
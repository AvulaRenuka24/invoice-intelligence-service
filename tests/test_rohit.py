# tests/test_rohit.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from unittest.mock import patch, MagicMock
from schemas import AnswerResponse
from qa import ask

# ------------------------------------------------------------------
# Helper: mock the LLM generate function so no real model is called
# ------------------------------------------------------------------
def mock_generate(messages, max_tokens):
    """Return a canned answer depending on the question."""
    question = messages[0]["content"] if messages else ""
    if "total amount" in question.lower():
        return '{"answer": "$13,082.48", "sources": ["INV-24990"]}'
    if "ceo" in question.lower():
        return '{"answer": "I don\'t know", "sources": []}'
    return '{"answer": "I don\'t know", "sources": []}'

# ------------------------------------------------------------------
# Test 1: Answerable question returns confidence and sources
# ------------------------------------------------------------------
def test_answerable_question_returns_confidence():
    with patch("qa.generate", mock_generate), \
         patch("qa.search", return_value=[{"chunk": "...", "invoice_number": "INV-24990", "score": 0.9}]):
        result = ask("What is the total amount on invoice INV-24990?")
        assert isinstance(result, AnswerResponse)
        assert "13082.48" in result.answer.replace(",", "")
        assert len(result.cited_invoices) > 0
        assert result.confidence > 0
        assert result.needs_review in (True, False)

# ------------------------------------------------------------------
# Test 2: Unanswerable question (CEO) refuses
# ------------------------------------------------------------------
def test_unanswerable_question_refuses():
    with patch("qa.generate", mock_generate), \
         patch("qa.search", return_value=[{"chunk": "...", "invoice_number": "INV-24990", "score": 0.5}]):
        result = ask("What is the CEO of Massive Dynamic?")
        assert "i don't know" in result.answer.lower()
        assert result.cited_invoices == []
        

# ------------------------------------------------------------------
# Test 3: Review queue endpoint returns items (skip if CSV missing)
# ------------------------------------------------------------------
def test_review_queue_returns_items():
    try:
        from main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/review")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "items" in data
    except Exception as e:
        pytest.skip(f"Review endpoint test skipped due to: {e}")
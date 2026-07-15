"""
schemas.py — Shared response models (Shared Task 1).

One file, one set of models, used by every endpoint in app.py.
Both Renuka's fields and Rohit's fields live here.

Planned breaking change (logged in CONFLICTS.md 2026-07-08):
  ``sources`` was renamed to ``cited_invoices`` in AnswerResponse.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Extraction schemas (Renuka Task 4 / Rohit Task 1)
# ---------------------------------------------------------------------------


class InvoiceFields(BaseModel):
    """
    Structured invoice data returned by llm_service.extract().

    Carries both the extracted fields and the extraction metadata so
    callers can route low-confidence results to the human review queue.
    """

    invoice_number: str = Field(default="", description="Invoice identifier.")
    vendor: str = Field(default="", description="Vendor or supplier name.")
    invoice_date: str = Field(default="", description="Invoice date (any format).")
    total_amount: float = Field(default=0.0, description="Total amount due.")
    currency: str = Field(default="", description="3-letter currency code.")
    line_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Individual line items (description + amount).",
    )

    # -- Renuka Task 4 fields --
    source: str = Field(
        default="llm",
        description="'llm' when the model produced a valid result; 'fallback' when regex was used.",
    )
    confidence: float = Field(
        default=0.0,
        description="Extraction confidence in [0.0, 1.0].",
    )
    needs_review: bool = Field(
        default=False,
        description="True when confidence is below the configured threshold.",
    )


class ExtractResponse(InvoiceFields):
    """
    HTTP response body for POST /extract.

    Extends InvoiceFields with Renuka's service metadata.
    """

    # -- Renuka Task 5 fields --
    provider: str = Field(default="", description="Active LLM provider name.")
    latency_ms: int = Field(default=0, description="End-to-end extraction latency in ms.")
    cache: str = Field(default="miss", description="'hit' or 'miss'.")


# ---------------------------------------------------------------------------
# QA / answer schemas (Rohit Task 1)
# ---------------------------------------------------------------------------


class AnswerResponse(BaseModel):
    """
    HTTP response body for POST /ask.

    Holds Rohit's trust signals (confidence, needs_review) and
    Renuka's service metadata (provider, latency_ms).

    Breaking change logged in CONFLICTS.md (2026-07-08):
        ``sources`` → ``cited_invoices``
    """

    answer: str = Field(description="The answer, or 'I don't know'.")
    confidence: float = Field(description="Answer confidence in [0.0, 1.0].")
    cited_invoices: List[str] = Field(
        description="Invoice numbers whose text grounded this answer."
    )
    needs_review: bool = Field(
        description="True when confidence is below the configured threshold."
    )
    provider: str = Field(description="Active LLM provider name.")
    latency_ms: int = Field(description="QA latency in milliseconds.")


# ---------------------------------------------------------------------------
# Human review queue schemas (Rohit Task 2)
# ---------------------------------------------------------------------------


class ReviewItem(BaseModel):
    """A single item in the human review queue."""

    id: int = Field(description="Unique database row ID.")
    invoice_number: str = Field(default="")
    vendor: str = Field(default="")
    total_amount: float = Field(default=0.0)
    currency: str = Field(default="")
    confidence: float = Field(description="Extraction confidence.")
    source: str = Field(description="'llm' or 'fallback'.")
    source_file: str = Field(default="", description="Original PDF filename.")
    review_status: str = Field(default="unreviewed")
    created_at: str = Field(default="")


class ReviewPatch(BaseModel):
    """Request body for PATCH /review/{id}."""

    action: str = Field(
        default="confirm",
        description="'confirm' to accept as-is; 'fix' to override field values.",
    )
    invoice_number: Optional[str] = Field(default=None)
    vendor: Optional[str] = Field(default=None)
    total_amount: Optional[float] = Field(default=None)
    reviewed_by: str = Field(default="user", description="Who performed the review.")


# ---------------------------------------------------------------------------
# Import job schemas (Rohit Tasks 3 & 4)
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    """Request body for POST /imports."""

    folder: str = Field(description="Path to a folder of PDF invoices to import.")


class JobStatus(BaseModel):
    """Response for GET /jobs/{job_id}."""

    job_id: str
    state: str = Field(
        description="'queued' | 'running' | 'done' | 'failed' | 'cancelled'"
    )
    folder: str = Field(default="")
    total: int = Field(default=0, description="Total PDF files found.")
    done: int = Field(default=0, description="Files processed so far (any outcome).")
    processed: int = Field(default=0, description="Successfully extracted.")
    duplicate: int = Field(default=0, description="Skipped as duplicates.")
    failed: int = Field(default=0, description="Failed with an error.")
    cancelled: int = Field(default=0, description="Cancelled before processing.")
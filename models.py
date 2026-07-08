"""
Task 2 – Pydantic Models for Invoice Extraction

Defines the Invoice and LineItem schemas used for structured
extraction and validation.
"""

from typing import List, Optional

from pydantic import BaseModel, Field



class LineItem(BaseModel):
    """A single line item on an invoice."""

    description: str = Field(default="")
    amount: float = Field(default=0.0)

class Invoice(BaseModel):
    """Structured invoice data extracted from a PDF."""

    invoice_number: str = Field(default="")
    vendor: str = Field(default="")
    invoice_date: str = Field(default="")
    total_amount: float = Field(default=0.0)
    currency: str = Field(default="")
    line_items: List[LineItem] = Field(default_factory=list)

class AnswerResponse(BaseModel):
    answer: str
    confidence: float         
    sources: list[str]          
    needs_review: bool          
    provider: str               
    latency_ms: int  
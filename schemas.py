from pydantic import BaseModel


class AnswerResponse(BaseModel):
    answer: str
    confidence: float
    cited_invoices: list[str]
    needs_review: bool
    provider: str
    latency_ms: int
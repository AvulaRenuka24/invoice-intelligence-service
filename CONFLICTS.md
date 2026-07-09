# Merge Conflicts Log

## 2026-07-08: Rename `sources` to `cited_invoices` in `AnswerResponse`
- **File:** `schemas.py`
- **What changed:** Renamed field `sources: list[str]` to `cited_invoices: list[str]`.
- **Why:** Shared Task 1 planned breaking change.
- **Who updated:** Rohit updated `qa.py` to use the new field name.
- **Tests:** Manual QA test passed; no automated tests affected.
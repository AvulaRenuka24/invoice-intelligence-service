# Merge Conflicts Log

## 2026-07-08: Rename `sources` to `cited_invoices` in `AnswerResponse`
- **File:** `schemas.py`
- **What changed:** Renamed field `sources: list[str]` to `cited_invoices: list[str]`.
- **Why:** Shared Task 1 planned breaking change.
- **Who updated:** Rohit updated `qa.py` to use the new field name.
- **Tests:** Manual QA test passed; no automated tests affected.

## 2026-07-15: Merge conflicts when integrating Renuka’s provider/circuit‑breaker
- **Files:** `main.py`, `extract.py`, `schemas.py`, `llm_service.py`
- **What happened:** Both had added separate endpoints and functions; the files diverged heavily.
- **Resolution:** Manually kept all endpoints (Rohit’s review queue, imports; Renuka’s health, metrics), merged the provider classes, and resolved duplicate imports.
- **Tests:** Restarted server and verified all endpoints returned correct JSON.
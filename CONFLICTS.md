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
## 2026-07-16: Merge conflict in data/extracted_invoices.csv
- **File:** `data/extracted_invoices.csv`
- **What happened:** Pulling `main` into `feature/renuka-task1-llm-service`
  conflicted on this generated data file — both branches had different
  extraction rows written to it.
- **Resolution:** Kept `main`'s version (`git checkout --theirs`), since
  this file is generated output, not hand-edited source.
- **Tests:** Verified `providers.py` and `llm_service.py` still had the
  correct transformers-import fix after the merge (`Select-String
  "transformers" *.py`); no test file affected by this conflict.
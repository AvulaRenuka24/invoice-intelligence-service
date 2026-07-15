# Reflection – Rohit

## What I owned
- Rohit Tasks 1–5: confidence scoring, human review queue, background folder import, resilience/cancellation, and integration with Renuka’s LLM service.
- End‑to‑end testing of the combined service.

## One thing I would do differently
- I would write mocked tests earlier in the week, so that CI could enforce passing tests on every PR from the start. Waiting until the end to add tests caused some manual verification overhead.

## One time I helped or was helped
- I helped Renuka resolve merge conflicts when her `llm_service.py` clashed with my extraction changes. We worked together in a live session to keep both sides’ intent intact.

## Shared Task 4 – Branch and PR workflow

All work was done in short-lived feature branches named `feature/<person>-<description>`. No one committed directly to `main`. Every change went through a pull request with review.

Examples:
- `feature/rohit-task1-confidence-refusal` – Rohit Task 1
- `feature/rohit-task2-review-queue` – Rohit Task 2–4
- `feature/renuka-task1-llm-service` – Renuka’s LLM service
- `feature/shared-rename-field` – Shared Task 1 breaking change
- `feature/week4-remaining-tasks` – Shared Tasks 2–3 and final fixes

Each PR included a description of what changed, why, and how it was tested. At least one approval was required before merging.

## Shared Task 5 – Code reviews

Both team members reviewed every PR. At least one PR included a formal “Request changes” with a concrete improvement (e.g., a missing edge case in the review queue PATCH endpoint). The author fixed the issue in follow‑up commits, the reviewer re‑reviewed, and then the PR was merged.

Key review example:
- Rohit’s review queue PR: Renuka requested a fix for the timestamp type error in `PATCH /review`. Rohit amended the commit, Renuka re‑approved, and the PR was merged.

## Shared Task 7 – Renuka’s reflection (to be completed by Renuka)

<!-- Renuka: write your half-page reflection here. Include what you owned, one thing you’d do differently, and one time you helped or were helped. -->
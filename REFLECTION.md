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

## What I owned

I owned the Week 4 LLM service improvements, including centralizing all model interactions into `llm_service.py`, implementing provider abstraction, retry logic with exponential backoff, request timeout handling, in-memory caching, circuit breaker support, and exposing `/health` and `/metrics` endpoints. I also updated the project documentation, tested the API endpoints, and helped integrate these changes with the rest of the invoice processing pipeline.

## One thing I would do differently

I would spend more time designing the overall architecture before starting implementation. During development, a few components had to be refactored as new requirements were introduced. Planning the interfaces and responsibilities earlier would have reduced rework and made integration smoother.

## One time I helped or was helped

I worked closely with Rohit while integrating our changes into a single codebase. During integration, we resolved merge conflicts between the LLM service and extraction pipeline together. We reviewed each other's code, discussed implementation decisions, and ensured that the final application worked correctly with both our contributions.

## What I learned

This project helped me understand how to build a production-oriented AI service rather than just an AI model. I learned about designing reusable services, implementing reliability features such as retries and circuit breakers, using Git branches and pull requests for collaborative development, resolving merge conflicts, and exposing AI functionality through well-designed REST APIs. It also gave me practical experience working in a team on a shared codebase.
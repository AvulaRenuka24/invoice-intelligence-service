"""
request_context.py — Request id contextvar (Renuka Task 5).

The FastAPI middleware in main.py sets this once per request; every
log line picks it up automatically without being passed through every
function call.
"""

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

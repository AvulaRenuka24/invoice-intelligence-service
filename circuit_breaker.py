"""
circuit_breaker.py — Circuit breaker (Renuka Task 3).
 
States: CLOSED -> OPEN -> HALF_OPEN -> (CLOSED or OPEN).
 
CLOSED:     calls go through normally.
OPEN:       calls are short-circuited (fallback used instantly) until
            the cool-off elapses.
HALF_OPEN:  one probe call is allowed through; success closes the
            breaker, failure reopens it.
"""
 
import time
from threading import Lock
 
 
class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
 
    def __init__(self, failure_threshold: int = 5, cooldown_s: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self._state = self.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = Lock()
 
    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN and self._opened_at is not None:
                if time.time() - self._opened_at >= self.cooldown_s:
                    self._state = self.HALF_OPEN
            return self._state
 
    def allow_call(self) -> bool:
        """CLOSED and HALF_OPEN let a call through; OPEN does not."""
        return self.state in (self.CLOSED, self.HALF_OPEN)
 
    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = self.CLOSED
            self._opened_at = None
 
    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == self.HALF_OPEN:
                # the probe call failed — reopen immediately
                self._state = self.OPEN
                self._opened_at = time.time()
            elif self._failures >= self.failure_threshold:
                self._state = self.OPEN
                self._opened_at = time.time()
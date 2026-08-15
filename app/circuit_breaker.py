"""
A per-endpoint circuit breaker that stops the gateway from hammering a target
endpoint that keeps failing.

States:
  - "closed"    : normal. Deliveries flow.
  - "open"      : tripped. Deliveries are blocked during a cooldown.
  - "half_open" : cooldown passed. One test delivery is allowed through.

Rules:
  - After FAILURE_THRESHOLD consecutive failures, trip to "open".
  - After COOLDOWN_SECONDS, move "open" -> "half_open" (allow one test).
  - A success resets everything to "closed".
  - A failure while "half_open" trips straight back to "open".
"""

from datetime import datetime, timedelta

FAILURE_THRESHOLD = 5      # trip after this many consecutive failures
COOLDOWN_SECONDS = 30      # stay "open" this long before testing again


def can_attempt_delivery(endpoint) -> bool:
    """Decide whether we're allowed to attempt delivery to this endpoint now."""
    if endpoint.circuit_state == "closed":
        return True

    if endpoint.circuit_state == "open":
        if endpoint.circuit_opened_at is not None:
            elapsed = datetime.utcnow() - endpoint.circuit_opened_at
            if elapsed >= timedelta(seconds=COOLDOWN_SECONDS):
                endpoint.circuit_state = "half_open"
                return True
        return False

    if endpoint.circuit_state == "half_open":
        return True

    return True


def record_success(endpoint) -> None:
    """A delivery succeeded: reset the breaker to healthy/closed."""
    endpoint.consecutive_failures = 0
    endpoint.circuit_state = "closed"
    endpoint.circuit_opened_at = None


def record_failure(endpoint) -> None:
    """A delivery failed: count it, and trip the breaker if needed."""
    endpoint.consecutive_failures += 1

    if endpoint.circuit_state == "half_open":
        endpoint.circuit_state = "open"
        endpoint.circuit_opened_at = datetime.utcnow()
        return

    if endpoint.consecutive_failures >= FAILURE_THRESHOLD:
        endpoint.circuit_state = "open"
        endpoint.circuit_opened_at = datetime.utcnow()

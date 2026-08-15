"""
The delivery job that runs inside the WORKER process (not the API).

Flow:
  - Check the endpoint's circuit breaker; if it's open, skip and mark "blocked".
  - Attempt delivery.
  - On success: mark "delivered" and reset the breaker.
  - On failure: count the failure toward the breaker, then raise an exception so
    RQ retries the job (with exponential backoff configured at enqueue time).
    When retries are exhausted, mark the event "failed".
"""

from sqlmodel import Session
from rq import get_current_job
from app.database import engine
from app.models import Event, Endpoint
from app.delivery import deliver_event
from app.circuit_breaker import can_attempt_delivery, record_success, record_failure


class DeliveryFailed(Exception):
    """Raised when a delivery attempt fails, to trigger an RQ retry."""
    pass


def deliver_event_task(event_id: int) -> str:
    with Session(engine) as session:
        event = session.get(Event, event_id)
        if event is None:
            return f"Event {event_id} not found"

        endpoint = session.get(Endpoint, event.endpoint_id)
        if endpoint is None:
            event.status = "failed"
            session.add(event)
            session.commit()
            return f"Endpoint for event {event_id} not found"

        # Circuit breaker: if the endpoint is tripped, don't even attempt delivery.
        if not can_attempt_delivery(endpoint):
            session.add(endpoint)
            event.status = "blocked"
            session.add(event)
            session.commit()
            return f"Event {event_id}: blocked — circuit open for endpoint {endpoint.id}"
        session.add(endpoint)
        session.commit()

        event.attempts += 1
        session.add(event)
        session.commit()
        session.refresh(event)

        success, detail = deliver_event(endpoint.url, event.payload)

        if success:
            event.status = "delivered"
            record_success(endpoint)
            session.add(event)
            session.add(endpoint)
            session.commit()
            return f"Event {event_id}: delivered on attempt {event.attempts}"

        # Delivery failed: count it toward the breaker.
        record_failure(endpoint)
        session.add(endpoint)
        session.commit()

        job = get_current_job()
        retries_left = getattr(job, "retries_left", 0) if job else 0

        if retries_left and retries_left > 0:
            # Retries remain: keep "pending" and raise so RQ retries after backoff.
            event.status = "pending"
            session.add(event)
            session.commit()
            raise DeliveryFailed(
                f"Event {event_id} attempt {event.attempts} failed ({detail}); "
                f"{retries_left} retries left; "
                f"endpoint failures={endpoint.consecutive_failures} state={endpoint.circuit_state}"
            )
        else:
            # No retries left: final failure.
            event.status = "failed"
            session.add(event)
            session.commit()
            return f"Event {event_id}: failed permanently after {event.attempts} attempts"

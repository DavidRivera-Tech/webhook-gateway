"""FastAPI application: receives webhook events, stores them, and enqueues
them for asynchronous delivery (with idempotency de-duplication)."""
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel

from app.database import init_db, get_session
from app.models import Endpoint, Event
from app.queue import delivery_queue
from app.tasks import deliver_event_task
from rq import Retry

app = FastAPI(
    title="Webhook Delivery Gateway",
    description="Async webhook gateway with retries, circuit breaker, and idempotency.",
    version="1.0.0",
)


class EndpointCreate(BaseModel):
    url: str
    name: str


class EventCreate(BaseModel):
    endpoint_id: int
    payload: str
    # optional idempotency key. If two events arrive with the
    # same key, the second is recognized as a duplicate and skipped.
    idempotency_key: Optional[str] = None


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def read_root():
    return {"service": "Webhook Delivery Gateway", "status": "running"}


@app.post("/endpoints", response_model=Endpoint, status_code=status.HTTP_201_CREATED)
def create_endpoint(data: EndpointCreate, session: Session = Depends(get_session)):
    endpoint = Endpoint(url=data.url, name=data.name)
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)
    return endpoint


@app.get("/endpoints", response_model=list[Endpoint])
def list_endpoints(session: Session = Depends(get_session)):
    return session.exec(select(Endpoint)).all()


@app.post("/webhooks", status_code=status.HTTP_202_ACCEPTED)
def receive_webhook(data: EventCreate, session: Session = Depends(get_session)):
    # Confirm the target endpoint exists.
    endpoint = session.get(Endpoint, data.endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {data.endpoint_id} not found",
        )

    # Idempotency check: if we have seen this key before, skip re-processing.
    # If the sender gave a key AND we've already seen it, this is a duplicate.
    # Return the ORIGINAL event instead of creating and delivering a new one.
    if data.idempotency_key:
        existing = session.exec(
            select(Event).where(Event.idempotency_key == data.idempotency_key)
        ).first()
        if existing:
            return {
                "message": "Duplicate ignored (idempotency key already seen)",
                "event_id": existing.id,
                "status": existing.status,
            }

    # Save the event as "pending".
    event = Event(
        endpoint_id=data.endpoint_id,
        payload=data.payload,
        idempotency_key=data.idempotency_key,
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    # Enqueue with retry + exponential backoff.
    delivery_queue.enqueue(
        deliver_event_task,
        event.id,
        retry=Retry(max=3, interval=[5, 25, 125]),
    )

    return {
        "message": "Event accepted and queued for delivery",
        "event_id": event.id,
        "status": event.status,
    }


@app.get("/events", response_model=list[Event])
def list_events(session: Session = Depends(get_session)):
    return session.exec(select(Event)).all()

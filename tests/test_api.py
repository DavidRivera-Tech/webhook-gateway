"""
Automated tests for the webhook gateway (pytest + FastAPI TestClient).
Runs against a temporary SQLite DB with the queue stubbed out — no Redis/Postgres needed.
"""

import os
os.environ["DATABASE_URL"] = "sqlite:///test_webhook.db"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, delete

from sqlmodel import Session
from app import main
from app.database import engine
from app.models import Endpoint, Event

# Create tables once for the whole test session.
SQLModel.metadata.create_all(engine)


@pytest.fixture
def client(monkeypatch):
    # Clear all data before each test for a clean slate.
    with Session(engine) as s:
        s.exec(delete(Event))
        s.exec(delete(Endpoint))
        s.commit()

    # Stub out the real queue so tests don't need Redis.
    monkeypatch.setattr(main.delivery_queue, "enqueue", lambda *a, **k: None)

    with TestClient(main.app) as c:
        yield c


def test_health_check(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


def test_create_endpoint(client):
    r = client.post("/endpoints", json={"url": "http://example.com", "name": "Test"})
    assert r.status_code == 201
    data = r.json()
    assert data["url"] == "http://example.com"
    assert data["circuit_state"] == "closed"


def test_webhook_to_missing_endpoint_returns_404(client):
    r = client.post("/webhooks", json={"endpoint_id": 999, "payload": "x"})
    assert r.status_code == 404


def test_webhook_creates_event(client):
    ep = client.post("/endpoints", json={"url": "http://example.com", "name": "T"}).json()
    r = client.post("/webhooks", json={"endpoint_id": ep["id"], "payload": "hello"})
    assert r.status_code == 202
    assert r.json()["status"] == "pending"


def test_idempotency_skips_duplicates(client):
    ep = client.post("/endpoints", json={"url": "http://example.com", "name": "T"}).json()
    body = {"endpoint_id": ep["id"], "payload": "x", "idempotency_key": "dupe-1"}
    r1 = client.post("/webhooks", json=body)
    r2 = client.post("/webhooks", json=body)
    assert "accepted" in r1.json()["message"].lower()
    assert "duplicate" in r2.json()["message"].lower()
    events = client.get("/events").json()
    matching = [e for e in events if e["idempotency_key"] == "dupe-1"]
    assert len(matching) == 1


def test_invalid_payload_returns_422(client):
    r = client.post("/webhooks", json={"endpoint_id": 1})
    assert r.status_code == 422

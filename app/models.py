"""
Database tables defined as Python classes (SQLModel). Each class is a table;
each attribute is a column.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Endpoint(SQLModel, table=True):
    """A target destination we can deliver webhooks to."""
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Circuit breaker state for this endpoint.
    consecutive_failures: int = Field(default=0)
    circuit_state: str = Field(default="closed")   # closed | open | half_open
    circuit_opened_at: Optional[datetime] = Field(default=None)


class Event(SQLModel, table=True):
    """An incoming webhook event we received and (eventually) deliver."""
    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint_id: int = Field(foreign_key="endpoint.id", index=True)
    payload: str
    status: str = Field(default="pending", index=True)  # pending|delivered|failed|blocked
    attempts: int = Field(default=0)

    # Optional idempotency key: duplicate sends with the same key are ignored.
    idempotency_key: Optional[str] = Field(default=None, index=True)

    received_at: datetime = Field(default_factory=datetime.utcnow)

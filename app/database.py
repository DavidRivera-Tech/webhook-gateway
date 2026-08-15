"""
Sets up the database connection. The URL is read from the DATABASE_URL
environment variable:

  - If DATABASE_URL is set (e.g. by Docker Compose), we use it -> PostgreSQL.
  - If it's not set, we fall back to local SQLite for easy development.

Using SQLModel means the same code runs on either database — switching is a
matter of configuration, not a code change.
"""

import os
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///webhook.db")

# SQLite needs this connect arg; PostgreSQL does not.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create all tables defined in models.py if they don't exist yet."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Hand out a database session for one request, then close it."""
    with Session(engine) as session:
        yield session

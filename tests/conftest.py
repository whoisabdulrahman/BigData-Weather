"""Shared pytest configuration.

Environment is configured *before* any application module is imported:

* ``STREAM_MODE=bus`` — deterministic in-memory transport for unit tests (DEC-002)
* ``DATABASE_URL``    — isolated SQLite file so unit tests never touch live services

Live end-to-end coverage lives in ``tests/test_live_pipeline_e2e.py``, which
spawns real processes against Dockerised PostgreSQL/PostGIS and Redpanda.
"""
import os
import pathlib
import tempfile

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "bwip_pytest.db"
if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()

os.environ["STREAM_MODE"] = "bus"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

import pytest  # noqa: E402

from apps.api.db.session import Base, SessionLocal, engine  # noqa: E402
import apps.api.models  # noqa: E402,F401
from scripts.seed_demo_incidents import seed_demo_incidents  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create the schema and seed deterministic demo data once per session."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo_incidents(db)
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def clean_stream_bus():
    from services.streaming.bus import stream_bus

    stream_bus.clear()
    yield
    stream_bus.clear()

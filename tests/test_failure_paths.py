"""Failure-path verification against the live infrastructure.

Covers the required failure modes without hiding them behind fake success:

* Redpanda unavailable  -> API returns 503 and does NOT report the observation as accepted
* Database unavailable  -> worker retries with backoff, dead-letters the message, stays alive
* Malformed message     -> see tests/test_live_pipeline_e2e.py (routed to weather.dlq.v1)
* Duplicate message     -> see tests/test_live_pipeline_e2e.py (single persisted observation)
"""
import sys
import time
import uuid

import httpx
import pytest

from apps.api.core.config import settings
from tests import live_utils
from tests.live_utils import (
    DEAD_BROKER_API_PORT,
    DLQ_TOPIC,
    RAW_TOPIC,
    consume_matching_sync,
    live_session_factory,
    publish_records_sync,
    start_process,
    stop_process,
    wait_for,
    wait_for_http,
)

pytestmark = pytest.mark.skipif(
    not live_utils.infra_available(),
    reason="Live infrastructure unavailable (PostgreSQL :5432 / Redpanda :9092 not reachable)",
)

DEAD_BROKER = "127.0.0.1:9099"
DEAD_DATABASE_URL = "postgresql://weather_user:weather_secure_dev_password@127.0.0.1:5433/weather_platform"


def _report_exists(report_id: str) -> bool:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        from apps.api.models.report import Report

        return db.query(Report).filter(Report.id == str(report_id)).first() is not None
    finally:
        db.close()
        engine.dispose()


def _report_with_text_exists(text: str) -> bool:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        from apps.api.models.report import Report

        return db.query(Report).filter(Report.text == text).first() is not None
    finally:
        db.close()
        engine.dispose()


def test_api_fails_clearly_when_redpanda_unavailable():
    """A down broker must surface as HTTP 503 — never as a fake 202."""
    assert not live_utils.tcp_open("127.0.0.1", 9099), "expected the decoy broker port to be closed"

    marker = f"E2E-FAIL-{uuid.uuid4().hex[:8]}"
    env_overrides = {
        "STREAM_MODE": "redpanda",
        "KAFKA_BOOTSTRAP_SERVERS": DEAD_BROKER,
        "DATABASE_URL": live_utils.live_database_url(),
        "PYTHONPATH": str(live_utils.ROOT),
    }
    api = start_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(DEAD_BROKER_API_PORT),
            "--log-level",
            "warning",
        ],
        **env_overrides,
    )
    try:
        wait_for_http(f"http://127.0.0.1:{DEAD_BROKER_API_PORT}/health", timeout=45)

        readiness = httpx.get(
            f"http://127.0.0.1:{DEAD_BROKER_API_PORT}/ready", timeout=30
        ).json()
        assert readiness["components"]["streaming"]["status"] == "unavailable"
        assert readiness["status"] == "degraded"

        started = time.monotonic()
        response = httpx.post(
            f"http://127.0.0.1:{DEAD_BROKER_API_PORT}/api/v1/citizen/reports",
            json={
                "text": f"{marker} observation while broker is down",
                "event_type": "RAIN",
                "latitude": 21.15,
                "longitude": 79.09,
                "state": "Maharashtra",
                "city": "Nagpur",
                "location_provenance": "gps",
            },
            timeout=60,
        )
        elapsed = time.monotonic() - started

        assert response.status_code == 503, response.text
        detail = response.json()["detail"]
        assert "Ingestion stream unavailable" in detail
        assert "NOT accepted" in detail
        assert elapsed < 55, f"publish failure must fail fast, took {elapsed:.1f}s"

        # No observation was persisted anywhere.
        assert not _report_with_text_exists(f"{marker} observation while broker is down")
    finally:
        stop_process(api)


def test_worker_retries_and_dead_letters_when_database_unavailable():
    """Database outage: bounded retries, message preserved in DLQ, worker survives."""
    assert not live_utils.tcp_open("127.0.0.1", 5433), "expected the decoy database port to be closed"

    marker = f"E2E-NODB-{uuid.uuid4().hex[:8]}"
    event_id = str(uuid.uuid4())
    envelope = {
        "event_id": event_id,
        "source": {"type": "citizen", "name": "citizen_portal", "external_id": marker},
        "observed_at": "2026-09-30T10:00:00+00:00",
        "ingested_at": "2026-09-30T10:00:00+00:00",
        "content": {"text": f"{marker} observation during database outage", "language": "en", "media": []},
        "location": {
            "latitude": 21.15,
            "longitude": 79.09,
            "city": "Nagpur",
            "state": "Maharashtra",
            "provenance": "gps",
            "confidence": 0.9,
        },
        "classification": {"event_type": "RAIN", "confidence": 0.8},
    }

    group_name = f"bwip-test-dead-db-{uuid.uuid4().hex[:8]}"
    worker = start_process(
        [sys.executable, "-m", "services.streaming.worker"],
        STREAM_MODE="redpanda",
        DATABASE_URL=DEAD_DATABASE_URL,
        KAFKA_BOOTSTRAP_SERVERS=settings.KAFKA_BOOTSTRAP_SERVERS,
        KAFKA_CONSUMER_GROUP=group_name,
        KAFKA_AUTO_OFFSET_RESET="latest",
        PYTHONPATH=str(live_utils.ROOT),
    )
    try:
        # Wait until the fresh consumer group is assigned partitions, otherwise
        # `latest` could resolve after our publish and the message would be skipped.
        assert wait_for(
            lambda: f"for group {group_name}" in live_utils.process_output(worker),
            timeout=40,
        ), f"worker never joined its consumer group\n{live_utils.process_output(worker)}"
        publish_records_sync(RAW_TOPIC, [envelope], key=event_id)

        dead_lettered = consume_matching_sync(
            DLQ_TOPIC,
            lambda message: str(message.get("message", {}).get("event_id")) == event_id,
            timeout=45,
        )
        assert dead_lettered, "message must be dead-lettered when the database is unavailable"
        error = dead_lettered[0]["error"]
        assert "Processing failed after" in error, error
        assert "attempts" in error

        assert worker.poll() is None, (
            f"worker must survive an infrastructure failure\n{live_utils.process_output(worker)}"
        )
        assert not _report_exists(event_id)
    finally:
        stop_process(worker)

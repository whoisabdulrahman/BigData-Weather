"""Live end-to-end pipeline verification against the running Docker services.

Demonstrates the required boundary crossing in a single test:

    Citizen Report -> FastAPI -> Redpanda `weather.raw.v1` -> Consumer
                  -> Processing -> PostgreSQL/PostGIS -> Incident -> API Retrieval

Every assertion is made against the physical system: the HTTP API, the real
Redpanda topic contents, the real PostgreSQL tables and the running API server.
"""
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
import pytest
from sqlalchemy import func

from apps.api.core.config import settings
from apps.api.models.incident import Incident, IncidentReport
from apps.api.models.report import Report
from tests import live_utils
from tests.live_utils import (
    DLQ_TOPIC,
    LIVE_API_PORT,
    RAW_TOPIC,
    consume_matching_sync,
    live_session_factory,
    publish_records_sync,
    start_process,
    stop_process,
    wait_for_http,
    wait_for_messages_processed,
    wait_for,
)

pytestmark = pytest.mark.skipif(
    not live_utils.infra_available(),
    reason="Live infrastructure unavailable (PostgreSQL :5432 / Redpanda :9092 not reachable)",
)

BASE_URL = f"http://127.0.0.1:{LIVE_API_PORT}"
EVENT_TYPE = "THUNDERSTORM"
CLEANUP_PREFIX = "E2E-%"


def _cleanup_previous_runs() -> None:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        report_ids = [
            row.id for row in db.query(Report.id).filter(Report.text.like(CLEANUP_PREFIX)).all()
        ]
        if not report_ids:
            return
        incident_ids = [
            row.incident_id
            for row in db.query(IncidentReport.incident_id)
            .filter(IncidentReport.report_id.in_(report_ids))
            .all()
        ]
        db.query(IncidentReport).filter(IncidentReport.report_id.in_(report_ids)).delete(
            synchronize_session=False
        )
        db.query(Report).filter(Report.id.in_(report_ids)).delete(synchronize_session=False)
        if incident_ids:
            db.query(Incident).filter(Incident.id.in_(incident_ids)).delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()
        engine.dispose()


def _fetch_report(report_id: str) -> Optional[Report]:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        report = db.query(Report).filter(Report.id == str(report_id)).first()
        if report is None:
            return None
        db.expunge(report)
        return report
    finally:
        db.close()
        engine.dispose()


def _fetch_incident_for_report(report_id: str) -> Optional[Incident]:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        link = (
            db.query(IncidentReport)
            .filter(IncidentReport.report_id == str(report_id))
            .first()
        )
        if link is None:
            return None
        incident = db.query(Incident).filter(Incident.id == link.incident_id).first()
        if incident is not None:
            db.expunge(incident)
        return incident
    finally:
        db.close()
        engine.dispose()


def _count_reports_with_text(text: str) -> int:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        return int(db.query(func.count(Report.id)).filter(Report.text == text).scalar() or 0)
    finally:
        db.close()
        engine.dispose()


def _count_reports_with_source(source_name: str) -> int:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        return int(
            db.query(func.count(Report.id))
            .filter(Report.source_name == source_name)
            .scalar()
            or 0
        )
    finally:
        db.close()
        engine.dispose()


def _incident_observation_count(incident_id: str) -> int:
    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        incident = db.query(Incident).filter(Incident.id == str(incident_id)).first()
        return int(incident.observation_count) if incident else -1
    finally:
        db.close()
        engine.dispose()


@pytest.fixture(scope="module")
def live_api():
    """Start a real API server and a real pipeline worker against Docker services."""
    env_overrides = {
        "STREAM_MODE": "redpanda",
        "DATABASE_URL": live_utils.live_database_url(),
        "KAFKA_BOOTSTRAP_SERVERS": settings.KAFKA_BOOTSTRAP_SERVERS,
        "PYTHONPATH": str(live_utils.ROOT),
    }

    worker = start_process(
        [sys.executable, "-m", "services.streaming.worker"],
        **env_overrides,
    )
    api = start_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(LIVE_API_PORT),
            "--log-level",
            "warning",
        ],
        **env_overrides,
    )

    try:
        health = wait_for_http(f"{BASE_URL}/health", timeout=45)
        assert health.json()["status"] == "ok"
        yield {"base_url": BASE_URL, "worker": worker, "api": api}
    finally:
        stop_process(api)
        stop_process(worker)


def test_e2e_full_pipeline_with_idempotency_and_aggregation(live_api):
    """Citizen Report → FastAPI → Redpanda → Consumer → PostgreSQL/PostGIS → Incident → API."""
    _cleanup_previous_runs()

    run_id = uuid.uuid4().hex[:10]
    marker = f"E2E-{run_id}"
    base_lat, base_lon = 22.5726, 88.3639  # Kolkata — away from seeded demo incidents
    observed = datetime.now(timezone.utc)

    payload_a = {
        "text": f"{marker} primary observation: sudden cloudburst near station road",
        "event_type": EVENT_TYPE,
        "observed_at": observed.isoformat(),
        "latitude": base_lat,
        "longitude": base_lon,
        "city": "Kolkata",
        "district": "Kolkata",
        "state": "West Bengal",
        "location_provenance": "gps",
    }

    # --- Boundary 1: Citizen Report -> FastAPI -------------------------------
    response = httpx.post(f"{BASE_URL}/api/v1/citizen/reports", json=payload_a, timeout=30)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["status"] == "ACCEPTED"
    assert accepted["stream_topic"] == "weather.raw.v1"
    assert accepted["transport"] == "redpanda", "API must publish to the live broker"
    event_id_a = accepted["id"]

    # --- Boundary 2: FastAPI -> Redpanda (physical message in the topic) ----
    in_topic = consume_matching_sync(
        RAW_TOPIC,
        lambda message: message.get("event_id") == event_id_a,
        timeout=25,
    )
    assert in_topic, "message never reached the Redpanda topic"
    assert in_topic[0]["content"]["text"] == payload_a["text"]

    # --- Boundary 3/4: Redpanda -> Consumer -> Processing -> PostgreSQL ------
    wait_for_messages_processed(in_topic)
    assert wait_for(lambda: _fetch_report(event_id_a) is not None), "report not persisted"

    report_a = _fetch_report(event_id_a)
    assert report_a is not None
    assert report_a.processing_status == "INCIDENT_CREATED"
    assert report_a.state == "West Bengal"
    assert report_a.report_hash is not None

    incident = _fetch_incident_for_report(event_id_a)
    assert incident is not None, "incident was not created"
    incident_id = str(incident.id)
    assert incident.observation_count == 1
    assert incident.event_type == EVENT_TYPE

    # --- Boundary 5: Incident -> API Retrieval ------------------------------
    detail = httpx.get(f"{BASE_URL}/api/v1/incidents/{incident_id}", timeout=10)
    assert detail.status_code == 200, detail.text
    assert detail.json()["observation_count"] == 1
    assert detail.json()["event_type"] == EVENT_TYPE

    listing = httpx.get(
        f"{BASE_URL}/api/v1/incidents", params={"event_type": EVENT_TYPE}, timeout=10
    )
    assert listing.status_code == 200, listing.text
    listed_ids = [item["id"] for item in listing.json()["items"]]
    assert incident_id in listed_ids, "incident missing from list API"

    analytics = httpx.get(f"{BASE_URL}/api/v1/analytics/summary", timeout=10)
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["total_active_incidents"] >= 1
    assert analytics.json()["events_by_type"].get(EVENT_TYPE, 0) >= 1

    # --- Step 6: idempotency — identical observation delivered again --------
    duplicate = httpx.post(f"{BASE_URL}/api/v1/citizen/reports", json=payload_a, timeout=30)
    assert duplicate.status_code == 202, duplicate.text
    duplicate_event_id = duplicate.json()["id"]

    duplicate_in_topic = consume_matching_sync(
        RAW_TOPIC,
        lambda message: message.get("event_id") == duplicate_event_id,
        timeout=25,
    )
    assert duplicate_in_topic, "duplicate message never reached the topic"
    wait_for_messages_processed(duplicate_in_topic)

    assert _count_reports_with_text(payload_a["text"]) == 1, (
        "duplicate delivery must not persist a second observation"
    )
    assert _fetch_report(duplicate_event_id) is None, (
        "duplicate event id must not exist in the reports table"
    )
    assert _incident_observation_count(incident_id) == 1, (
        "duplicate delivery must not increment the incident observation count"
    )

    # --- Step 7: aggregation — two more compatible observations -------------
    payload_b = {
        "text": f"{marker} secondary observation: waterlogging reported at crossing",
        "event_type": EVENT_TYPE,
        "observed_at": (observed + timedelta(minutes=10)).isoformat(),
        "latitude": base_lat + 0.010,
        "longitude": base_lon + 0.020,
        "city": "Kolkata",
        "district": "Kolkata",
        "state": "West Bengal",
        "location_provenance": "user_selected",
    }
    response_b = httpx.post(f"{BASE_URL}/api/v1/citizen/reports", json=payload_b, timeout=30)
    assert response_b.status_code == 202, response_b.text
    event_id_b = response_b.json()["id"]

    in_topic_b = consume_matching_sync(
        RAW_TOPIC, lambda message: message.get("event_id") == event_id_b, timeout=25
    )
    assert in_topic_b
    wait_for_messages_processed(in_topic_b)
    assert wait_for(lambda: _fetch_report(event_id_b) is not None)

    assert _count_reports_with_text(payload_a["text"]) + _count_reports_with_text(
        payload_b["text"]
    ) == 2, "expected exactly two observations"
    incident_after_b = _fetch_incident_for_report(event_id_b)
    assert incident_after_b is not None
    assert str(incident_after_b.id) == incident_id, "second observation must join the same incident"
    assert _incident_observation_count(incident_id) == 2

    payload_c = {
        "text": f"{marker} third observation: tree uprooted near crossing",
        "event_type": EVENT_TYPE,
        "observed_at": (observed + timedelta(minutes=20)).isoformat(),
        "latitude": base_lat + 0.020,
        "longitude": base_lon + 0.040,
        "city": "Kolkata",
        "district": "Kolkata",
        "state": "West Bengal",
        "location_provenance": "user_selected",
    }
    response_c = httpx.post(f"{BASE_URL}/api/v1/citizen/reports", json=payload_c, timeout=30)
    assert response_c.status_code == 202, response_c.text
    event_id_c = response_c.json()["id"]

    in_topic_c = consume_matching_sync(
        RAW_TOPIC, lambda message: message.get("event_id") == event_id_c, timeout=25
    )
    assert in_topic_c
    wait_for_messages_processed(in_topic_c)
    assert wait_for(lambda: _fetch_report(event_id_c) is not None)

    incident_after_c = _fetch_incident_for_report(event_id_c)
    assert str(incident_after_c.id) == incident_id, "third observation must update the same incident"
    assert _incident_observation_count(incident_id) == 3

    engine, session_factory = live_session_factory()
    db = session_factory()
    try:
        total_reports = (
            db.query(func.count(Report.id)).filter(Report.text.like(f"{marker}%")).scalar()
        )
        total_incidents = (
            db.query(func.count(func.distinct(Incident.id)))
            .join(IncidentReport, IncidentReport.incident_id == Incident.id)
            .join(Report, Report.id == IncidentReport.report_id)
            .filter(Report.text.like(f"{marker}%"))
            .scalar()
        )
        assert int(total_reports) == 3, "3 observations expected in PostgreSQL"
        assert int(total_incidents) == 1, "1 incident expected in PostgreSQL"
    finally:
        db.close()
        engine.dispose()

    final_listing = httpx.get(
        f"{BASE_URL}/api/v1/incidents", params={"event_type": EVENT_TYPE}, timeout=10
    )
    matching = [
        item for item in final_listing.json()["items"] if item["id"] == incident_id
    ]
    assert matching and matching[0]["observation_count"] == 3


def test_e2e_malformed_message_is_dead_lettered(live_api):
    """Malformed broker message -> weather.dlq.v1, never persisted."""
    malformed_event_id = f"malformed-{uuid.uuid4().hex}"
    broken_source = f"broken_source_{uuid.uuid4().hex[:8]}"
    publish_records_sync(
        RAW_TOPIC,
        [{"event_id": malformed_event_id, "source": {"name": broken_source}}],
        key=malformed_event_id,
    )

    dead_lettered = consume_matching_sync(
        DLQ_TOPIC,
        lambda message: str(message.get("message", {}).get("event_id")) == malformed_event_id,
        timeout=30,
    )
    assert dead_lettered, "malformed message was not routed to weather.dlq.v1"
    assert "missing required field" in dead_lettered[0]["error"]

    assert _count_reports_with_source(broken_source) == 0, (
        "malformed message must not persist"
    )


def test_e2e_duplicate_delivery_persists_single_observation(live_api):
    """The same broker message delivered twice produces exactly one observation."""
    run_id = uuid.uuid4().hex[:10]
    marker = f"E2E-DUP-{run_id}"
    event_id = str(uuid.uuid4())
    observed = datetime.now(timezone.utc).isoformat()

    envelope = {
        "event_id": event_id,
        "source": {"type": "citizen", "name": "citizen_portal", "external_id": marker},
        "observed_at": observed,
        "ingested_at": observed,
        "content": {"text": f"{marker} duplicate delivery probe", "language": "en", "media": []},
        "location": {
            "latitude": 22.9000,
            "longitude": 88.7000,
            "city": "Barrackpore",
            "state": "West Bengal",
            "provenance": "gps",
            "confidence": 0.9,
        },
        "classification": {"event_type": EVENT_TYPE, "confidence": 0.8},
    }

    publish_records_sync(RAW_TOPIC, [envelope, envelope], key=event_id)

    in_topic = consume_matching_sync(
        RAW_TOPIC,
        lambda message: message.get("event_id") == event_id,
        timeout=30,
        min_matches=2,
    )
    assert len(in_topic) == 2, "expected both deliveries to be present in the topic"

    wait_for_messages_processed(in_topic, timeout=30)
    assert wait_for(lambda: _fetch_report(event_id) is not None, timeout=30)

    assert _count_reports_with_text(f"{marker} duplicate delivery probe") == 1
    incident = _fetch_incident_for_report(event_id)
    assert incident is not None
    assert _incident_observation_count(str(incident.id)) == 1, (
        "duplicate delivery must not increment observation_count"
    )

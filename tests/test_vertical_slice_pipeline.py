import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.main import app
from apps.api.db.session import Base
from apps.api.models.report import Report
from apps.api.models.incident import Incident, IncidentReport
from services.streaming.bus import stream_bus
from services.streaming.producer import producer
from services.streaming.consumer import EventConsumer
from services.processing.pipeline import ObservationPipelineEngine


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_bus():
    stream_bus.clear()
    yield
    stream_bus.clear()


client = TestClient(app)


def test_1_and_2_citizen_report_accepted_and_published():
    """Requirement 1 & 2: Valid citizen report enters system and is published to topic."""
    payload = {
        "text": "Severe waterlogging near Banjara Hills road no 12, water level knee high.",
        "event_type": "FLOOD",
        "latitude": 17.4156,
        "longitude": 78.4357,
        "state": "Telangana",
        "city": "Hyderabad",
        "location_provenance": "gps",
        "media_urls": ["https://storage.bwip.gov.in/media/flooding_hyd.jpg"],
    }

    response = client.post("/api/v1/citizen/reports", json=payload)
    assert response.status_code == 202
    data = response.json()

    assert data["status"] == "ACCEPTED"
    assert data["processing_status"] == "ACCEPTED"
    assert data["stream_topic"] == "weather.raw.v1"
    assert "VALIDATED" in data["lifecycle"]
    assert "PUBLISHED" in data["lifecycle"]

    # Verify message in topic
    messages = stream_bus.get_messages("weather.raw.v1")
    assert len(messages) == 1
    assert messages[0]["topic"] == "weather.raw.v1"
    assert messages[0]["payload"]["content"]["text"] == payload["text"]
    assert messages[0]["payload"]["classification"]["event_type"] == "FLOOD"


def test_3_4_5_consumer_persists_report_and_creates_incident(test_db):
    """Requirement 3, 4, 5: Consumer receives event, persists report, and creates incident."""
    pipeline = ObservationPipelineEngine(spatial_radius_meters=15000.0, temporal_window_hours=6.0)

    now = datetime.now(timezone.utc)
    event_id = str(uuid4())
    raw_event = {
        "event_id": event_id,
        "source": {"type": "citizen", "name": "citizen_portal", "external_id": "BWIP-TEST-001"},
        "observed_at": now.isoformat(),
        "ingested_at": now.isoformat(),
        "content": {"text": "Flash flooding on outer ring road", "language": "en", "media": []},
        "location": {
            "latitude": 17.3850,
            "longitude": 78.4867,
            "city": "Hyderabad",
            "state": "Telangana",
            "provenance": "gps",
            "confidence": 0.9,
        },
        "classification": {"event_type": "FLOOD", "confidence": 0.85},
    }

    result = pipeline.process_raw_observation(raw_event, test_db)

    assert result["status"] == "INCIDENT_CREATED"
    assert result["is_duplicate"] is False
    assert result["observation_count"] == 1

    # Verify Report persisted in database
    persisted_report = test_db.query(Report).filter(Report.id == event_id).first()
    assert persisted_report is not None
    assert persisted_report.city == "Hyderabad"
    assert persisted_report.event_type == "FLOOD"
    assert persisted_report.processing_status == "INCIDENT_CREATED"

    # Verify Incident created in database
    persisted_incident = test_db.query(Incident).filter(Incident.id == result["incident_id"]).first()
    assert persisted_incident is not None
    assert persisted_incident.observation_count == 1
    assert persisted_incident.status == "ACTIVE"

    # Verify IncidentReport relationship bridge
    link = test_db.query(IncidentReport).filter(
        IncidentReport.incident_id == persisted_incident.id,
        IncidentReport.report_id == persisted_report.id,
    ).first()
    assert link is not None
    assert link.is_primary is True


def test_6_second_nearby_report_updates_existing_incident(test_db):
    """
    Requirement 6: Second nearby observation within space/time window
    updates the existing incident rather than creating a new one (Observation != Incident).
    """
    pipeline = ObservationPipelineEngine(spatial_radius_meters=15000.0, temporal_window_hours=6.0)
    base_time = datetime.now(timezone.utc)

    # Observation 1
    event1 = {
        "event_id": str(uuid4()),
        "source": {"type": "citizen", "name": "user_alpha", "external_id": "BWIP-A"},
        "observed_at": base_time.isoformat(),
        "content": {"text": "Torrential rain and highway submerged near Begumpet", "language": "en"},
        "location": {"latitude": 17.4400, "longitude": 78.4700, "city": "Hyderabad", "state": "Telangana"},
        "classification": {"event_type": "FLOOD", "confidence": 0.8},
    }
    res1 = pipeline.process_raw_observation(event1, test_db)
    incident_id = res1["incident_id"]

    # Observation 2: 3 km away, 20 minutes later, same event type
    event2 = {
        "event_id": str(uuid4()),
        "source": {"type": "social", "name": "imd_observer", "external_id": "BWIP-B"},
        "observed_at": (base_time + timedelta(minutes=20)).isoformat(),
        "content": {"text": "Water levels rising near Secunderabad station", "language": "en"},
        "location": {"latitude": 17.4330, "longitude": 78.5000, "city": "Secunderabad", "state": "Telangana"},
        "classification": {"event_type": "FLOOD", "confidence": 0.9},
    }
    res2 = pipeline.process_raw_observation(event2, test_db)

    assert res2["status"] == "INCIDENT_UPDATED"
    assert res2["incident_id"] == incident_id  # Clustered into SAME incident!
    assert res2["observation_count"] == 2

    # Verify DB state
    all_reports = test_db.query(Report).all()
    assert len(all_reports) == 2  # 2 distinct observations

    all_incidents = test_db.query(Incident).all()
    assert len(all_incidents) == 1  # 1 clustered incident
    assert all_incidents[0].observation_count == 2


def test_7_idempotency_duplicate_message_suppression(test_db):
    """
    Requirement 7: Duplicate delivery of the exact same event does NOT create duplicate observation.
    """
    pipeline = ObservationPipelineEngine(spatial_radius_meters=15000.0, temporal_window_hours=6.0)
    now = datetime.now(timezone.utc)

    event = {
        "event_id": str(uuid4()),
        "source": {"type": "citizen", "name": "citizen_portal", "external_id": "RETRY-MSG-101"},
        "observed_at": now.isoformat(),
        "content": {"text": "Severe cyclone gust destroying trees", "language": "en"},
        "location": {"latitude": 17.6868, "longitude": 83.2185, "city": "Visakhapatnam", "state": "Andhra Pradesh"},
        "classification": {"event_type": "CYCLONE", "confidence": 0.95},
    }

    # First delivery
    res1 = pipeline.process_raw_observation(event, test_db)
    assert res1["status"] == "INCIDENT_CREATED"
    assert res1["is_duplicate"] is False

    # Second delivery (identical message / duplicate delivery from message broker retry)
    res2 = pipeline.process_raw_observation(event, test_db)
    assert res2["status"] == "DUPLICATE_IGNORED"
    assert res2["is_duplicate"] is True

    # Third delivery
    res3 = pipeline.process_raw_observation(event, test_db)
    assert res3["status"] == "DUPLICATE_IGNORED"

    # Verify database still has exactly 1 report and 1 incident
    assert test_db.query(Report).count() == 1
    assert test_db.query(Incident).count() == 1
    assert test_db.query(Incident).first().observation_count == 1


@pytest.mark.asyncio
async def test_8_malformed_event_routed_to_dlq():
    """
    Requirement 8: Malformed events are safely rejected and routed to weather.dlq.v1.
    """
    test_consumer = EventConsumer(topic="weather.raw.v1")

    # Missing location and classification
    malformed_event = {
        "event_id": "corrupted-payload",
        "source": {"name": "faulty_source"},
        # missing observed_at, location, classification
    }

    await test_consumer.handle_event({"topic": "weather.raw.v1", "payload": malformed_event})

    # Verify DLQ received the failed event
    dlq_messages = stream_bus.get_dlq_messages()
    assert len(dlq_messages) == 1
    assert dlq_messages[0]["origin_topic"] == "weather.raw.v1"
    assert "missing required field" in dlq_messages[0]["error"]

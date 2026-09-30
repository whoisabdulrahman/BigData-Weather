"""Deterministic demo seed (DEC-002, AGENTS §31).

Seeded incidents are clearly marked with ``metadata_json.demo = true`` so demo
data is always distinguishable from live pipeline data.

Run:
    python -m scripts.seed_demo_incidents
"""
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
from uuid import UUID

from apps.api.models.incident import Incident

DEMO_INCIDENTS: List[Dict[str, Any]] = [
    {
        "id": "a1000000-0000-0000-0000-000000000001",
        "title": "Severe Urban Waterlogging & Flash Flooding",
        "event_type": "FLOOD",
        "severity": "HIGH",
        "confidence": 0.91,
        "latitude": 17.3850,
        "longitude": 78.4867,
        "radius_meters": 8000.0,
        "city": "Hyderabad",
        "district": "Hyderabad",
        "state": "Telangana",
        "status": "ACTIVE",
        "verification_status": "AI_CORROBORATED",
        "observation_count": 18,
        "summary": "Intense cloudburst resulting in 94mm rainfall over 2 hours causing inundation of key arterial roads.",
        "hours_ago": 3,
        "updated_minutes_ago": 12,
        "metadata": {"rainfall_mm_2h": 94.2, "corroborating_stations": ["HYD_BEGUMPET_AWS"]},
    },
    {
        "id": "a1000000-0000-0000-0000-000000000002",
        "title": "Severe Cyclonic Wind & Torrential Downpour",
        "event_type": "CYCLONE",
        "severity": "CRITICAL",
        "confidence": 0.96,
        "latitude": 17.6868,
        "longitude": 83.2185,
        "radius_meters": 25000.0,
        "city": "Visakhapatnam",
        "district": "Visakhapatnam",
        "state": "Andhra Pradesh",
        "status": "ACTIVE",
        "verification_status": "HUMAN_VERIFIED",
        "observation_count": 42,
        "summary": "Coastal squall with gusts reaching 85 km/h, heavy swell and sustained rainfall.",
        "hours_ago": 6,
        "updated_minutes_ago": 5,
        "metadata": {"wind_gust_kmh": 85, "surge_height_m": 1.2},
    },
    {
        "id": "a1000000-0000-0000-0000-000000000003",
        "title": "Dense Advection Fog Causing Low Runway Visual Range",
        "event_type": "FOG",
        "severity": "MODERATE",
        "confidence": 0.88,
        "latitude": 28.5562,
        "longitude": 77.1000,
        "radius_meters": 15000.0,
        "city": "New Delhi",
        "district": "South West Delhi",
        "state": "Delhi",
        "status": "ACTIVE",
        "verification_status": "AI_CORROBORATED",
        "observation_count": 27,
        "summary": "RVR drops below 100 meters at IGI airport; highway visibility degraded below 50m.",
        "hours_ago": 8,
        "updated_minutes_ago": 60,
        "metadata": {"visibility_m": 75, "temperature_c": 11.4},
    },
]


def seed_demo_incidents(db) -> Dict[str, int]:
    """Insert missing demo incidents. Idempotent: existing ids are skipped."""
    now = datetime.now(timezone.utc)
    inserted = 0
    skipped = 0

    for record in DEMO_INCIDENTS:
        incident_id = str(UUID(record["id"]))
        if db.query(Incident).filter(Incident.id == incident_id).first():
            skipped += 1
            continue

        metadata = dict(record["metadata"])
        metadata["demo"] = True
        metadata["fixture"] = "competition_demo_v1"

        db.add(
            Incident(
                id=incident_id,
                title=record["title"],
                event_type=record["event_type"],
                severity=record["severity"],
                confidence=record["confidence"],
                latitude=record["latitude"],
                longitude=record["longitude"],
                radius_meters=record["radius_meters"],
                city=record["city"],
                district=record["district"],
                state=record["state"],
                started_at=now - timedelta(hours=record["hours_ago"]),
                last_updated_at=now - timedelta(minutes=record["updated_minutes_ago"]),
                status=record["status"],
                verification_status=record["verification_status"],
                observation_count=record["observation_count"],
                summary=record["summary"],
                metadata_json=metadata,
                created_at=now - timedelta(hours=record["hours_ago"]),
                updated_at=now - timedelta(minutes=record["updated_minutes_ago"]),
            )
        )
        inserted += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped}


def main() -> int:
    from apps.api.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = seed_demo_incidents(db)
        print(f"Demo incidents seeded: {result}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

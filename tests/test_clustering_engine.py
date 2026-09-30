from datetime import datetime, timezone, timedelta
from uuid import uuid4
from apps.api.schemas.reports import (
    CanonicalReport,
    ReportSource,
    SourceType,
    ReportContent,
    ReportLocation,
    LocationProvenance,
    ReportClassification,
    WeatherEventType,
)
from services.processing.clustering import IncidentClusteringEngine, haversine_distance_meters


def create_sample_report(
    lat: float, lon: float, event: WeatherEventType, observed_at: datetime
) -> CanonicalReport:
    return CanonicalReport(
        id=uuid4(),
        source=ReportSource(type=SourceType.CITIZEN, name="citizen_app"),
        observed_at=observed_at,
        content=ReportContent(text="Heavy flash flood on highway"),
        location=ReportLocation(
            latitude=lat,
            longitude=lon,
            city="Hyderabad",
            state="Telangana",
            provenance=LocationProvenance.GPS,
            confidence=0.9,
        ),
        classification=ReportClassification(event_type=event, confidence=0.88),
    )


def test_haversine_distance():
    # Distance between two known points in Hyderabad (~5.5 km)
    d = haversine_distance_meters(17.3850, 78.4867, 17.4300, 78.4500)
    assert 5000.0 < d < 7000.0


def test_observation_clusters_into_single_incident():
    """
    Validates Core Invariant:
    Two observations of the same event nearby within time window belong to 1 incident.
    Observation Count increments to 2.
    """
    engine = IncidentClusteringEngine(spatial_radius_meters=10000.0, temporal_window_hours=4.0)
    active_incidents = []
    base_time = datetime.now(timezone.utc)

    # Observation 1
    report1 = create_sample_report(17.3850, 78.4867, WeatherEventType.FLOOD, base_time)
    incident1, is_new1 = engine.cluster_report(report1, active_incidents)

    assert is_new1 is True
    assert incident1.observation_count == 1
    assert len(active_incidents) == 1

    # Observation 2 (2km away, 15 minutes later, same event type)
    report2 = create_sample_report(
        17.3950, 78.4950, WeatherEventType.FLOOD, base_time + timedelta(minutes=15)
    )
    incident2, is_new2 = engine.cluster_report(report2, active_incidents)

    assert is_new2 is False
    assert incident2.id == incident1.id
    assert incident2.observation_count == 2
    assert len(active_incidents) == 1  # Still 1 incident for 2 observations!


def test_distant_observation_spawns_separate_incident():
    """Observations far away in distance must create separate incidents."""
    engine = IncidentClusteringEngine(spatial_radius_meters=10000.0, temporal_window_hours=4.0)
    active_incidents = []
    base_time = datetime.now(timezone.utc)

    # Report in Hyderabad
    report_hyd = create_sample_report(17.3850, 78.4867, WeatherEventType.FLOOD, base_time)
    inc_hyd, _ = engine.cluster_report(report_hyd, active_incidents)

    # Report in Delhi (over 1000km away)
    report_delhi = create_sample_report(28.6139, 77.2090, WeatherEventType.FLOOD, base_time)
    inc_delhi, is_new = engine.cluster_report(report_delhi, active_incidents)

    assert is_new is True
    assert inc_delhi.id != inc_hyd.id
    assert len(active_incidents) == 2

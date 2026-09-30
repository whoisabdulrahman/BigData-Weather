import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import uuid4
from apps.api.schemas.reports import CanonicalReport, WeatherEventType
from apps.api.schemas.incidents import (
    IncidentBase,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    VerificationStatus,
)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class IncidentClusteringEngine:
    """
    Groups heterogeneous weather observations into clustered Incidents.
    Preserves the fundamental domain invariant:
    Observation/Report is NOT an Incident. Multiple observations belong to an incident.
    """

    def __init__(self, spatial_radius_meters: float = 15000.0, temporal_window_hours: float = 6.0):
        self.spatial_radius_meters = spatial_radius_meters
        self.temporal_window = timedelta(hours=temporal_window_hours)

    def find_matching_incident(
        self, report: CanonicalReport, active_incidents: List[IncidentResponse]
    ) -> Optional[Tuple[IncidentResponse, float]]:
        """
        Finds the closest compatible active incident within space and time boundaries.
        Returns (incident, distance_meters) or None.
        """
        best_match: Optional[IncidentResponse] = None
        min_distance = float("inf")

        for inc in active_incidents:
            # 1. Event type compatibility
            if inc.event_type != report.classification.event_type:
                continue

            # 2. Time window check
            time_diff = abs(report.observed_at - inc.last_updated_at)
            if time_diff > self.temporal_window:
                continue

            # 3. Spatial radius check
            dist = haversine_distance_meters(
                report.location.latitude,
                report.location.longitude,
                inc.latitude,
                inc.longitude,
            )
            if dist <= self.spatial_radius_meters and dist < min_distance:
                min_distance = dist
                best_match = inc

        if best_match:
            return best_match, min_distance
        return None

    def cluster_report(
        self, report: CanonicalReport, active_incidents: List[IncidentResponse]
    ) -> Tuple[IncidentResponse, bool]:
        """
        Assigns report to an existing incident, or spawns a new Incident cluster.
        Returns: (incident, is_new_incident)
        """
        match = self.find_matching_incident(report, active_incidents)

        if match:
            incident, _ = match
            # Update incident aggregations
            incident.observation_count += 1
            incident.last_updated_at = max(incident.last_updated_at, report.observed_at)
            incident.updated_at = datetime.now(timezone.utc)
            # Increase confidence with corroborated independent reports
            incident.confidence = min(0.99, incident.confidence + 0.05)
            return incident, False

        # Create new incident cluster
        now = datetime.now(timezone.utc)
        new_incident = IncidentResponse(
            id=uuid4(),
            title=f"Observed {report.classification.event_type.value} Event in {report.location.city or report.location.state}",
            event_type=report.classification.event_type,
            severity=IncidentSeverity.MODERATE,
            confidence=max(0.5, report.classification.confidence),
            latitude=report.location.latitude,
            longitude=report.location.longitude,
            radius_meters=self.spatial_radius_meters,
            city=report.location.city,
            district=report.location.district,
            state=report.location.state or "India",
            started_at=report.observed_at,
            last_updated_at=report.observed_at,
            status=IncidentStatus.ACTIVE,
            verification_status=VerificationStatus.UNCONFIRMED,
            observation_count=1,
            summary=report.content.text[:200] if report.content.text else None,
            metadata={"initial_source": report.source.name},
            created_at=now,
            updated_at=now,
        )
        active_incidents.append(new_incident)
        return new_incident, True

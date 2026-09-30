import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional
from uuid import uuid4
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.models.report import Report
from apps.api.models.incident import Incident, IncidentReport
from apps.api.schemas.reports import WeatherEventType
from services.processing.clustering import haversine_distance_meters
from apps.api.core.logging import logger


def compute_report_hash(
    source_name: str,
    text: Optional[str],
    observed_at: str,
    latitude: float,
    longitude: float,
    event_type: str,
) -> str:
    """Computes SHA-256 fingerprint for idempotency and duplicate observation detection."""
    content_str = f"{source_name}|{text or ''}|{observed_at}|{latitude:.4f}|{longitude:.4f}|{event_type}"
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


class ObservationPipelineEngine:
    """
    End-to-End Observation Ingestion, Idempotency, Persistence, and Incident Clustering Pipeline.
    Strictly enforces:
    1. Idempotency: Duplicate delivery of the same report does NOT create duplicate observation or increment incident.
    2. Observation != Incident: Multiple observations link to one incident cluster.
    3. Explicit lifecycle progression: VALIDATED -> ACCEPTED -> PUBLISHED -> PROCESSED -> PERSISTED -> INCIDENT_ASSOCIATED.
    """

    def __init__(self, spatial_radius_meters: float = 15000.0, temporal_window_hours: float = 6.0):
        self.spatial_radius_meters = spatial_radius_meters
        self.temporal_window = timedelta(hours=temporal_window_hours)

    def _commit_or_suppress_duplicate(
        self, db: Session, report_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Commit, collapsing a concurrent duplicate-delivery race into a
        DUPLICATE_IGNORED result instead of an error (DB-level idempotency)."""
        try:
            db.commit()
            return None
        except IntegrityError as integrity_error:
            db.rollback()
            existing_report = db.query(Report).filter(Report.report_hash == report_hash).first()
            if existing_report is None:
                raise integrity_error
            link = (
                db.query(IncidentReport)
                .filter(IncidentReport.report_id == existing_report.id)
                .first()
            )
            logger.warning(
                f"[Pipeline] Idempotency: duplicate delivery raced the unique index "
                f"(Hash: {report_hash[:8]}..., Report ID: {existing_report.id})"
            )
            return {
                "status": "DUPLICATE_IGNORED",
                "is_duplicate": True,
                "report_id": existing_report.id,
                "incident_id": link.incident_id if link else None,
                "message": "Duplicate event suppressed by unique report_hash index.",
            }

    def process_raw_observation(
        self, payload: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        # 1. Validation check
        if not payload or not isinstance(payload, dict):
            raise ValueError("Payload must be a non-empty JSON object")

        required_keys = ["source", "observed_at", "location", "classification"]
        for key in required_keys:
            if key not in payload:
                raise ValueError(f"Malformed event envelope: missing required field '{key}'")

        source = payload["source"]
        location = payload["location"]
        classification = payload["classification"]
        content = payload.get("content", {})

        if not isinstance(source, dict):
            raise ValueError("Malformed event envelope: 'source' must be an object")
        if not isinstance(location, dict):
            raise ValueError("Malformed event envelope: 'location' must be an object")
        if not isinstance(classification, dict):
            raise ValueError("Malformed event envelope: 'classification' must be an object")
        if not isinstance(content, dict):
            raise ValueError("Malformed event envelope: 'content' must be an object")
        for nested_key in ("latitude", "longitude"):
            if nested_key not in location:
                raise ValueError(f"Malformed event envelope: missing required field 'location.{nested_key}'")

        source_name = source.get("name", "unknown")
        source_type = source.get("type", "citizen")
        external_id = source.get("external_id")
        text = content.get("text")
        observed_at_str = payload["observed_at"]
        try:
            observed_at = datetime.fromisoformat(observed_at_str.replace("Z", "+00:00"))
        except Exception:
            raise ValueError(f"Invalid timestamp format: {observed_at_str}")

        lat = float(location["latitude"])
        lon = float(location["longitude"])
        event_type = classification.get("event_type", "OTHER")

        # 2. Idempotency Boundary Check
        report_hash = compute_report_hash(
            source_name=source_name,
            text=text,
            observed_at=observed_at_str,
            latitude=lat,
            longitude=lon,
            event_type=event_type,
        )

        existing_report = (
            db.query(Report).filter(Report.report_hash == report_hash).first()
        )
        if existing_report:
            logger.info(
                f"[Pipeline] Idempotency: Duplicate observation detected (Hash: {report_hash[:8]}..., Report ID: {existing_report.id})"
            )
            # Find associated incident
            link = (
                db.query(IncidentReport)
                .filter(IncidentReport.report_id == existing_report.id)
                .first()
            )
            return {
                "status": "DUPLICATE_IGNORED",
                "is_duplicate": True,
                "report_id": existing_report.id,
                "incident_id": link.incident_id if link else None,
                "message": "Duplicate event successfully suppressed by idempotency layer.",
            }

        # 3. Persist new Report
        report_id = payload.get("event_id") or str(uuid4())
        new_report = Report(
            id=report_id,
            source_type=source_type,
            source_name=source_name,
            external_id=external_id,
            report_hash=report_hash,
            text=text,
            language=content.get("language", "en"),
            observed_at=observed_at,
            latitude=lat,
            longitude=lon,
            location_provenance=location.get("provenance", "unknown"),
            location_confidence=float(location.get("confidence", 0.0)),
            city=location.get("city"),
            district=location.get("district"),
            state=location.get("state") or "India",
            event_type=event_type,
            event_confidence=float(classification.get("confidence", 0.5)),
            media_urls=content.get("media", []),
            processing_status="PERSISTED",
            metadata_json=payload.get("metadata", {}),
        )
        db.add(new_report)
        db.flush()

        # 4. Search Candidate Incidents for Clustering
        active_incidents = (
            db.query(Incident)
            .filter(
                Incident.event_type == event_type,
                Incident.status == "ACTIVE",
            )
            .all()
        )

        best_match: Optional[Incident] = None
        min_distance = float("inf")

        def ensure_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        for inc in active_incidents:
            # Check temporal window
            time_diff = abs(ensure_utc(observed_at) - ensure_utc(inc.last_updated_at))
            if time_diff > self.temporal_window:
                continue


            # Check spatial distance
            dist = haversine_distance_meters(lat, lon, inc.latitude, inc.longitude)
            if dist <= self.spatial_radius_meters and dist < min_distance:
                min_distance = dist
                best_match = inc

        if best_match:
            # Associate observation with existing incident
            best_match.observation_count += 1
            last_updated_utc = ensure_utc(best_match.last_updated_at)
            observed_utc = ensure_utc(observed_at)
            best_match.last_updated_at = max(last_updated_utc, observed_utc)
            best_match.updated_at = datetime.now(timezone.utc)
            best_match.confidence = min(0.99, float(best_match.confidence) + 0.04)


            # Link bridge entity
            link = IncidentReport(
                incident_id=best_match.id,
                report_id=new_report.id,
                association_score=max(0.5, 1.0 - (min_distance / self.spatial_radius_meters)),
                is_primary=False,
            )
            db.add(link)
            new_report.processing_status = "INCIDENT_ASSOCIATED"
            suppressed = self._commit_or_suppress_duplicate(db, report_hash)
            if suppressed is not None:
                return suppressed

            logger.info(
                f"[Pipeline] Report {new_report.id} clustered into existing Incident {best_match.id} (Total observations: {best_match.observation_count})"
            )
            return {
                "status": "INCIDENT_UPDATED",
                "is_duplicate": False,
                "report_id": new_report.id,
                "incident_id": best_match.id,
                "observation_count": best_match.observation_count,
            }

        # 5. Create new Incident Cluster
        now = datetime.now(timezone.utc)
        location_label = location.get("city") or location.get("state") or "India"
        new_incident = Incident(
            id=str(uuid4()),
            title=f"Observed {event_type} Incident in {location_label}",
            event_type=event_type,
            severity="MODERATE",
            confidence=max(0.6, float(classification.get("confidence", 0.6))),
            latitude=lat,
            longitude=lon,
            radius_meters=self.spatial_radius_meters,
            city=location.get("city"),
            district=location.get("district"),
            state=location.get("state") or "India",
            started_at=observed_at,
            last_updated_at=observed_at,
            status="ACTIVE",
            verification_status="UNCONFIRMED",
            observation_count=1,
            summary=text[:200] if text else None,
            created_at=now,
            updated_at=now,
        )
        db.add(new_incident)
        db.flush()

        link = IncidentReport(
            incident_id=new_incident.id,
            report_id=new_report.id,
            association_score=1.0,
            is_primary=True,
        )
        db.add(link)
        new_report.processing_status = "INCIDENT_CREATED"
        suppressed = self._commit_or_suppress_duplicate(db, report_hash)
        if suppressed is not None:
            return suppressed

        logger.info(
            f"[Pipeline] Spawned new Incident {new_incident.id} for Report {new_report.id}"
        )
        return {
            "status": "INCIDENT_CREATED",
            "is_duplicate": False,
            "report_id": new_report.id,
            "incident_id": new_incident.id,
            "observation_count": 1,
        }


pipeline_engine = ObservationPipelineEngine()

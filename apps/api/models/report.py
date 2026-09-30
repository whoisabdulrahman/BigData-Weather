import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Float,
    Numeric,
    Boolean,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from apps.api.db.session import Base


def generate_uuid():
    return str(uuid.uuid4())


class Report(Base):
    """
    Core Domain Model: Raw and Normalized Observation.
    Invariant: Observation/Report is NOT an Incident. Multiple observations belong to an incident.
    """
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_type = Column(String(50), nullable=False)  # citizen, social, weather_api, dataset, web
    source_name = Column(String(100), nullable=False)
    external_id = Column(String(255), index=True, nullable=True)
    report_hash = Column(String(64), index=True, unique=True, nullable=True)  # Idempotency / exact duplicate hash

    text = Column(Text, nullable=True)
    language = Column(String(10), default="en")
    translated_text = Column(Text, nullable=True)

    observed_at = Column(DateTime(timezone=True), nullable=False)
    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_provenance = Column(String(50), default="unknown")  # gps, user_selected, metadata, geocoded, weather_grid, unknown
    location_confidence = Column(Numeric(4, 3), default=0.0)

    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), nullable=False)

    event_type = Column(String(50), index=True, nullable=False)  # RAIN, FLOOD, THUNDERSTORM, CYCLONE, FOG, etc.
    event_confidence = Column(Numeric(4, 3), default=0.0)

    raw_object_key = Column(Text, nullable=True)
    media_urls = Column(JSON, default=list)

    # Idempotency and Duplication status
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(String(36), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)

    # Explicit lifecycle state progression
    processing_status = Column(
        String(50),
        default="VALIDATED",
        nullable=False
    )  # VALIDATED -> ACCEPTED -> PUBLISHED -> PROCESSED -> PERSISTED -> INCIDENT_ASSOCIATED

    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_reports_geo", "latitude", "longitude"),
        Index("ix_reports_observed_at", "observed_at"),
        Index("ix_reports_source_external", "source_type", "external_id"),
    )

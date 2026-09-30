import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Float,
    Numeric,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from apps.api.db.session import Base


def generate_uuid():
    return str(uuid.uuid4())


class Incident(Base):
    """
    Core Domain Model: Clustered Weather Incident.
    Aggregates multiple observations bounded in space and time.
    """
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    event_type = Column(String(50), index=True, nullable=False)
    severity = Column(String(20), default="MODERATE", nullable=False)  # LOW, MODERATE, HIGH, CRITICAL
    confidence = Column(Numeric(4, 3), default=0.5, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Float, default=5000.0)

    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    state = Column(String(100), index=True, nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    last_updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    status = Column(String(50), default="ACTIVE", index=True, nullable=False)  # ACTIVE, CONTAINED, RESOLVED, REJECTED
    verification_status = Column(
        String(50), default="UNCONFIRMED", index=True, nullable=False
    )  # UNCONFIRMED, AI_CORROBORATED, HUMAN_VERIFIED, HUMAN_REJECTED

    observation_count = Column(Integer, default=1, nullable=False)
    summary = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    reports = relationship("IncidentReport", back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_incidents_geo", "latitude", "longitude"),
        Index("ix_incidents_started_at", "started_at"),
        Index("ix_incidents_state_event", "state", "event_type"),
    )


class IncidentReport(Base):
    """
    Bridge entity linking Observations (Reports) to Incidents.
    """
    __tablename__ = "incident_reports"

    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), primary_key=True)
    association_score = Column(Numeric(4, 3), default=1.0)
    is_primary = Column(Boolean, default=False)
    linked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    incident = relationship("Incident", back_populates="reports")

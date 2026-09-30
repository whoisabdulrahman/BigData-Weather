import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Numeric,
    ForeignKey,
    JSON,
    Index,
)
from apps.api.db.session import Base


def generate_uuid():
    return str(uuid.uuid4())


class VerificationResult(Base):
    """
    Evidence-backed verification outcome for an observation or incident.
    """
    __tablename__ = "verification_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=True, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True, index=True)

    # Multi-dimensional signal scores
    source_score = Column(Numeric(4, 3), default=0.0)
    content_score = Column(Numeric(4, 3), default=0.0)
    location_score = Column(Numeric(4, 3), default=0.0)
    temporal_score = Column(Numeric(4, 3), default=0.0)
    weather_correlation_score = Column(Numeric(4, 3), default=0.0)
    media_score = Column(Numeric(4, 3), default=0.0)
    cross_report_score = Column(Numeric(4, 3), default=0.0)
    duplicate_risk = Column(Numeric(4, 3), default=0.0)

    overall_confidence = Column(Numeric(4, 3), nullable=False)
    status = Column(
        String(50), nullable=False
    )  # UNCONFIRMED, AI_CORROBORATED, HUMAN_VERIFIED, HUMAN_REJECTED
    reasons = Column(JSON, default=list)
    model_version = Column(String(50), default="verify-v1.0")

    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

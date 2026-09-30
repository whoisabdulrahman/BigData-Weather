from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.models.incident import Incident
from apps.api.models.report import Report

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_SEVERITY_RANK = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}


class AnalyticsSummary(BaseModel):
    total_active_incidents: int
    total_observations_last_24h: int
    critical_alerts_count: int
    ai_corroborated_ratio: float
    human_verified_count: int
    events_by_type: Dict[str, int]
    top_affected_states: List[Dict[str, Any]]
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="Operational Analytics Summary",
    description=(
        "Aggregated key performance indicators and event distributions for dashboard cards. "
        "All values are computed from the operational database."
    ),
)
async def get_analytics_summary(db: Session = Depends(get_db)) -> AnalyticsSummary:
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    total_active_incidents = (
        db.query(func.count(Incident.id)).filter(Incident.status == "ACTIVE").scalar() or 0
    )
    total_incidents = db.query(func.count(Incident.id)).scalar() or 0

    total_observations_24h = (
        db.query(func.count(Report.id)).filter(Report.observed_at >= since_24h).scalar() or 0
    )

    critical_alerts = (
        db.query(func.count(Incident.id))
        .filter(Incident.status == "ACTIVE", Incident.severity == "CRITICAL")
        .scalar()
        or 0
    )

    corroborated = (
        db.query(func.count(Incident.id))
        .filter(
            Incident.verification_status.in_(["AI_CORROBORATED", "HUMAN_VERIFIED"])
        )
        .scalar()
        or 0
    )
    human_verified = (
        db.query(func.count(Incident.id))
        .filter(Incident.verification_status == "HUMAN_VERIFIED")
        .scalar()
        or 0
    )

    ratio = round(corroborated / total_incidents, 2) if total_incidents else 0.0

    event_rows = (
        db.query(Incident.event_type, func.count(Incident.id))
        .group_by(Incident.event_type)
        .all()
    )
    events_by_type = {event_type: int(count) for event_type, count in event_rows}

    state_rows = (
        db.query(Incident.state, Incident.severity, func.count(Incident.id))
        .group_by(Incident.state, Incident.severity)
        .all()
    )
    state_totals: Dict[str, Dict[str, Any]] = {}
    for state_name, severity, count in state_rows:
        entry = state_totals.setdefault(
            state_name, {"state": state_name, "incidents": 0, "severity": severity}
        )
        entry["incidents"] += int(count)
        if _SEVERITY_RANK.get(severity, 0) > _SEVERITY_RANK.get(entry["severity"], 0):
            entry["severity"] = severity
    top_affected_states = sorted(
        state_totals.values(), key=lambda item: item["incidents"], reverse=True
    )[:5]

    return AnalyticsSummary(
        total_active_incidents=total_active_incidents,
        total_observations_last_24h=total_observations_24h,
        critical_alerts_count=critical_alerts,
        ai_corroborated_ratio=ratio,
        human_verified_count=human_verified,
        events_by_type=events_by_type,
        top_affected_states=top_affected_states,
        last_updated=now,
    )

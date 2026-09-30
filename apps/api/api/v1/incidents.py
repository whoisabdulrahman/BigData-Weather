from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.models.incident import Incident
from apps.api.schemas.incidents import (
    IncidentListResponse,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    VerificationStatus,
)
from apps.api.schemas.reports import WeatherEventType
from apps.api.core.logging import logger

router = APIRouter(prefix="/incidents", tags=["Incidents"])


def _ensure_utc(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def incident_to_response(incident: Incident) -> IncidentResponse:
    return IncidentResponse(
        id=UUID(str(incident.id)),
        title=incident.title,
        event_type=WeatherEventType(incident.event_type),
        severity=IncidentSeverity(incident.severity),
        confidence=float(incident.confidence),
        latitude=incident.latitude,
        longitude=incident.longitude,
        radius_meters=incident.radius_meters or 5000.0,
        city=incident.city,
        district=incident.district,
        state=incident.state,
        started_at=_ensure_utc(incident.started_at),
        last_updated_at=_ensure_utc(incident.last_updated_at),
        status=IncidentStatus(incident.status),
        verification_status=VerificationStatus(incident.verification_status),
        observation_count=incident.observation_count,
        summary=incident.summary,
        metadata=incident.metadata_json or {},
        created_at=_ensure_utc(incident.created_at),
        updated_at=_ensure_utc(incident.updated_at),
    )


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List weather incidents",
    description=(
        "Retrieve clustered weather incidents from the operational database "
        "with event, severity, lifecycle, verification and geo filters."
    ),
)
async def list_incidents(
    event_type: Optional[WeatherEventType] = Query(None, description="Filter by event type"),
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity level"),
    status_filter: Optional[IncidentStatus] = Query(None, alias="status", description="Filter by incident lifecycle status"),
    verification_status: Optional[VerificationStatus] = Query(None, description="Filter by verification status"),
    state: Optional[str] = Query(None, description="Filter by Indian State"),
    city: Optional[str] = Query(None, description="Filter by City"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    query = db.query(Incident)

    if event_type:
        query = query.filter(Incident.event_type == event_type.value)
    if severity:
        query = query.filter(Incident.severity == severity.value)
    if status_filter:
        query = query.filter(Incident.status == status_filter.value)
    if verification_status:
        query = query.filter(Incident.verification_status == verification_status.value)
    if state:
        query = query.filter(Incident.state.ilike(state))
    if city:
        query = query.filter(Incident.city.ilike(city))

    total = query.count()
    rows = (
        query.order_by(Incident.last_updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return IncidentListResponse(
        total=total,
        items=[incident_to_response(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Get incident details",
    description="Fetch single clustered weather incident by UUID",
)
async def get_incident(incident_id: UUID, db: Session = Depends(get_db)) -> IncidentResponse:
    incident = db.query(Incident).filter(Incident.id == str(incident_id)).first()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    return incident_to_response(incident)

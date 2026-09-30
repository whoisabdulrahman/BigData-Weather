from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from apps.api.schemas.reports import WeatherEventType


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class VerificationStatus(str, Enum):
    UNCONFIRMED = "UNCONFIRMED"
    AI_CORROBORATED = "AI_CORROBORATED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    HUMAN_REJECTED = "HUMAN_REJECTED"


class IncidentBase(BaseModel):
    title: str = Field(..., description="Descriptive headline of the incident")
    event_type: WeatherEventType
    severity: IncidentSeverity = IncidentSeverity.MODERATE
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_meters: float = Field(default=5000.0)
    city: Optional[str] = None
    district: Optional[str] = None
    state: str
    started_at: datetime
    status: IncidentStatus = IncidentStatus.ACTIVE
    verification_status: VerificationStatus = VerificationStatus.UNCONFIRMED
    observation_count: int = Field(default=1, ge=1)
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentResponse(IncidentBase):
    id: UUID
    last_updated_at: datetime
    created_at: datetime
    updated_at: datetime


class IncidentFilter(BaseModel):
    event_type: Optional[WeatherEventType] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    verification_status: Optional[VerificationStatus] = None
    state: Optional[str] = None
    city: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class IncidentListResponse(BaseModel):
    total: int
    items: List[IncidentResponse]
    limit: int
    offset: int

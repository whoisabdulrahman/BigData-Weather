from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    CITIZEN = "citizen"
    SOCIAL = "social"
    WEATHER_API = "weather_api"
    DATASET = "dataset"
    WEB = "web"


class LocationProvenance(str, Enum):
    GPS = "gps"
    USER_SELECTED = "user_selected"
    METADATA = "metadata"
    GEOCODED = "geocoded"
    WEATHER_GRID = "weather_grid"
    UNKNOWN = "unknown"


class WeatherEventType(str, Enum):
    RAIN = "RAIN"
    FLOOD = "FLOOD"
    THUNDERSTORM = "THUNDERSTORM"
    HEATWAVE = "HEATWAVE"
    FOG = "FOG"
    CYCLONE = "CYCLONE"
    DUST_STORM = "DUST_STORM"
    STRONG_WIND = "STRONG_WIND"
    HAILSTORM = "HAILSTORM"
    LANDSLIDE = "LANDSLIDE"
    OTHER = "OTHER"


class ReportSource(BaseModel):
    type: SourceType = Field(..., description="Source origin type")
    name: str = Field(..., description="Source identifier name, e.g. 'citizen_portal', 'imd_api', 'social_x'")
    external_id: Optional[str] = Field(default=None, description="External record or post ID")


class ReportContent(BaseModel):
    text: Optional[str] = Field(default=None, description="Raw observation text")
    language: Optional[str] = Field(default="en", description="Detected language code")
    translated_text: Optional[str] = Field(default=None, description="English translated text")
    media: List[str] = Field(default_factory=list, description="List of media storage URLs")


class ReportLocation(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude")
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    provenance: LocationProvenance = Field(default=LocationProvenance.UNKNOWN)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ReportClassification(BaseModel):
    event_type: WeatherEventType = Field(default=WeatherEventType.OTHER)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CanonicalReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source: ReportSource
    observed_at: datetime
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: ReportContent
    location: ReportLocation
    classification: ReportClassification
    is_duplicate: bool = False
    duplicate_of: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CitizenReportCreate(BaseModel):
    text: str = Field(..., min_length=5, max_length=2000, description="Citizen's weather observation report")
    event_type: WeatherEventType = Field(default=WeatherEventType.OTHER, description="Observed weather event type")
    observed_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Time the event was observed"
    )
    latitude: float = Field(..., ge=6.0, le=38.0, description="Latitude (restricted to India bounds 6°N - 38°N)")
    longitude: float = Field(..., ge=68.0, le=98.0, description="Longitude (restricted to India bounds 68°E - 98°E)")
    location_provenance: LocationProvenance = Field(
        default=LocationProvenance.USER_SELECTED,
        description="Provenance of the coordinates (gps or user_selected)"
    )
    city: Optional[str] = Field(default=None, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    state: str = Field(..., min_length=2, max_length=100, description="Indian State or Union Territory")
    media_urls: List[str] = Field(default_factory=list, max_length=5, description="Uploaded media reference URLs")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("State cannot be empty")
        return cleaned


class CitizenReportResponse(BaseModel):
    id: UUID
    reference_number: str
    status: str = "ACCEPTED"
    processing_status: str = "ACCEPTED"
    stream_topic: str = "weather.raw.v1"
    transport: str = Field(
        default="stream_bus",
        description="Actual delivery transport used: 'redpanda' (live broker) or 'stream_bus' (demo/test mode)",
    )
    lifecycle: List[str] = Field(
        default=["VALIDATED", "ACCEPTED", "PUBLISHED"],
        description="Explicit lifecycle state progression"
    )
    message: str = "Report validated, accepted, and published to ingestion stream."
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


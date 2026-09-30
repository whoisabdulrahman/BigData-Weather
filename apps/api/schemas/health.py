from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Current overall service health")
    environment: str = Field(..., description="Active environment name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current UTC timestamp"
    )


class ComponentHealth(BaseModel):
    status: str = Field(..., description="Status of the individual component (healthy/degraded/unavailable)")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optional diagnostic details")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Service readiness status (ready/not_ready)")
    components: Dict[str, ComponentHealth] = Field(..., description="Readiness of dependencies")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current UTC timestamp"
    )

"""Pydantic request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.state import Incident

SIMULATION_NOTE = (
    "Simulated: this state exists only in this process's memory. "
    "It does not represent any real AWS resource, failure or recovery."
)


class FailureRequest(BaseModel):
    """Body of POST /api/demo/simulate-failure (all fields optional)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(default="manual demo failure", min_length=1, max_length=200)
    severity: Literal["low", "medium", "high"] = "medium"


class IncidentOut(BaseModel):
    id: int
    reason: str
    severity: Literal["low", "medium", "high"]
    status: Literal["open", "resolved"]
    started_at: datetime
    resolved_at: datetime | None = None
    simulated: Literal[True] = True
    source: str = "local-simulation"

    @classmethod
    def from_incident(cls, incident: Incident) -> IncidentOut:
        return cls(
            id=incident.id,
            reason=incident.reason,
            severity=incident.severity,
            status=incident.status,
            started_at=incident.started_at,
            resolved_at=incident.resolved_at,
        )


class IncidentsResponse(BaseModel):
    count: int
    open_count: int
    all_simulated: Literal[True] = True
    note: str = SIMULATION_NOTE
    incidents: list[IncidentOut]


class DemoActionResponse(BaseModel):
    message: str
    simulated: Literal[True] = True
    note: str = SIMULATION_NOTE
    incident: IncidentOut


class HealthResponse(BaseModel):
    """Process liveness only. It is deliberately independent of the simulated failure state."""

    status: Literal["ok"] = "ok"
    service: str = "cloudrescue"
    version: str
    timestamp: datetime


class SimulatedServiceState(BaseModel):
    state: Literal["healthy", "failed"]
    since: datetime
    open_incident_id: int | None = None
    simulated: Literal[True] = True


class AwsInfo(BaseModel):
    """Real-AWS section. Kept apart from the simulation on purpose."""

    integration_implemented: Literal[False] = False
    configured: bool
    region: str | None = None
    status: Literal["not_checked"] = "not_checked"
    note: str = (
        "No AWS API calls are made in this phase. 'configured' only means a future target "
        "(region and instance id) was described via environment variables."
    )


class StatusResponse(BaseModel):
    service: str = "cloudrescue"
    version: str
    timestamp: datetime
    runtime_mode: Literal["local-simulation"] = "local-simulation"
    environment: str
    simulated_service: SimulatedServiceState
    aws: AwsInfo


class RootResponse(BaseModel):
    name: str = "CloudRescue"
    description: str
    version: str
    environment: str
    runtime_mode: Literal["local-simulation"] = "local-simulation"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    endpoints: dict[str, str]
    warning: str

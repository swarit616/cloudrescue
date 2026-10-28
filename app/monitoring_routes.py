"""Read-only API for externally received monitoring incidents."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict

from app.monitoring import MonitoringIncident

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class MonitoringIncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fingerprint: str
    alertname: str
    reason: str
    severity: str
    source: str
    status: Literal["open", "resolved"]
    started_at: datetime
    alert_starts_at: datetime | None
    alert_ends_at: datetime | None
    resolved_at: datetime | None
    last_received_at: datetime | None

    @classmethod
    def from_incident(cls, incident: MonitoringIncident) -> MonitoringIncidentOut:
        return cls.model_validate(incident)


class MonitoringIncidentsResponse(BaseModel):
    count: int
    total_count: int
    open_count: int
    resolved_count: int
    storage: Literal["in-memory"] = "in-memory"
    note: str = "Received monitoring incidents are cleared when this application restarts."
    incidents: list[MonitoringIncidentOut]


@router.get("/incidents", response_model=MonitoringIncidentsResponse)
def monitoring_incidents(
    request: Request,
    status: Annotated[Literal["open", "resolved"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MonitoringIncidentsResponse:
    """List actual received monitoring incidents, newest first."""

    store = request.app.state.monitoring
    items = store.incidents(status=status)[:limit]
    total, open_count = store.counts()

    return MonitoringIncidentsResponse(
        count=len(items),
        total_count=total,
        open_count=open_count,
        resolved_count=total - open_count,
        incidents=[MonitoringIncidentOut.from_incident(item) for item in items],
    )

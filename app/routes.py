"""HTTP endpoints."""

from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response

from app import __version__
from app.logging_config import LOGGER_NAME, log_event
from app.models import (
    AwsInfo,
    DemoActionResponse,
    FailureRequest,
    HealthResponse,
    IncidentOut,
    IncidentsResponse,
    RootResponse,
    SimulatedServiceState,
    StatusResponse,
)
from app.state import InvalidTransition

router = APIRouter()
logger = logging.getLogger(f"{LOGGER_NAME}.routes")


def require_demo_access(
    request: Request, x_demo_token: Annotated[str | None, Header()] = None
) -> None:
    """Guard for demo endpoints: can be switched off, and optionally token-protected."""
    settings = request.app.state.settings
    if not settings.demo_endpoints_enabled:
        raise HTTPException(
            status_code=403,
            detail="Demo endpoints are disabled (CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED=false)",
        )
    if settings.demo_token and not (
        x_demo_token and hmac.compare_digest(x_demo_token.encode(), settings.demo_token.encode())
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Demo-Token")


DemoGuard = Depends(require_demo_access)


@router.get("/", response_model=RootResponse, tags=["info"])
def root(request: Request) -> RootResponse:
    """Project information and links to the interactive API docs."""
    return RootResponse(
        description=(
            "A local incident/recovery simulation. Nothing here talks to AWS; "
            "see /docs for the API and README.md for the roadmap."
        ),
        version=__version__,
        environment=request.app.state.settings.environment,
        endpoints={
            "health": "GET /health",
            "status": "GET /api/status",
            "incidents": "GET /api/incidents",
            "simulate_failure": "POST /api/demo/simulate-failure",
            "recover": "POST /api/demo/recover",
            "metrics": "GET /metrics",
        },
        warning=(
            "Demo endpoints are for local use. Disable them "
            "(CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED=false) or protect them before any public deployment."
        ),
    )


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Liveness: the process is running. Not affected by the simulated failure."""
    return HealthResponse(version=__version__, timestamp=datetime.now(UTC))


@router.get(
    "/api/status",
    response_model=StatusResponse,
    tags=["status"],
    responses={503: {"model": StatusResponse, "description": "The SIMULATED service is failed"}},
)
def status(request: Request, response: Response) -> StatusResponse:
    """Simulated service state and real-AWS configuration, reported separately.

    Returns HTTP 503 (same body) while a simulated failure is active, so probes and
    scripts see an unhealthy service. The AWS section is unaffected by the simulation.
    """
    settings = request.app.state.settings
    healthy, since, incident = request.app.state.simulation.current()
    if not healthy:
        response.status_code = 503
    return StatusResponse(
        version=__version__,
        timestamp=datetime.now(UTC),
        environment=settings.environment,
        simulated_service=SimulatedServiceState(
            state="healthy" if healthy else "failed",
            since=since,
            open_incident_id=incident.id if incident else None,
        ),
        aws=AwsInfo(configured=settings.aws_configured, region=settings.aws_region),
    )


@router.get("/api/incidents", response_model=IncidentsResponse, tags=["incidents"])
def incidents(
    request: Request,
    status: Annotated[Literal["open", "resolved"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> IncidentsResponse:
    """Incident history, newest first. Every incident is a local simulation."""
    simulation = request.app.state.simulation
    items = simulation.incidents(status=status, limit=limit)
    return IncidentsResponse(
        count=len(items),
        open_count=simulation.counts()[1],
        incidents=[IncidentOut.from_incident(i) for i in items],
    )


@router.post(
    "/api/demo/simulate-failure",
    response_model=DemoActionResponse,
    status_code=201,
    tags=["demo"],
    dependencies=[DemoGuard],
    responses={409: {"description": "Already failed"}},
)
def simulate_failure(
    request: Request, body: Annotated[FailureRequest | None, Body()] = None
) -> DemoActionResponse:
    """Put the SIMULATED service into a failed state (in memory only)."""
    body = body or FailureRequest()
    try:
        incident = request.app.state.simulation.simulate_failure(body.reason, body.severity)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.app.state.metrics.record_failure(body.severity)
    log_event(
        logger, logging.WARNING, "simulation.failure_started",
        incident_id=incident.id, severity=incident.severity, simulated=True,
    )  # fmt: skip
    return DemoActionResponse(
        message="Simulated failure started", incident=IncidentOut.from_incident(incident)
    )


@router.post(
    "/api/demo/recover",
    response_model=DemoActionResponse,
    tags=["demo"],
    dependencies=[DemoGuard],
    responses={409: {"description": "Already healthy"}},
)
def recover(request: Request) -> DemoActionResponse:
    """Restore the SIMULATED service. This does not recover anything in AWS."""
    try:
        incident = request.app.state.simulation.recover()
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    request.app.state.metrics.record_recovery()
    log_event(logger, logging.INFO, "simulation.recovered", incident_id=incident.id, simulated=True)
    return DemoActionResponse(
        message="Simulated recovery completed", incident=IncidentOut.from_incident(incident)
    )


@router.get("/metrics", tags=["metrics"], response_class=Response)
def metrics(request: Request) -> Response:
    """Prometheus exposition format."""
    payload, content_type = request.app.state.metrics.render()
    return Response(content=payload, media_type=content_type)

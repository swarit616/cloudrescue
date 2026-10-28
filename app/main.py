"""Application factory. Run with ``uvicorn app.main:app``."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.alertmanager import router as alertmanager_router
from app.config import Settings
from app.logging_config import configure_logging, log_event, request_id_var
from app.metrics import Metrics
from app.monitoring import MonitoringStore
from app.routes import router
from app.state import SimulationState

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_QUIET = {"/metrics", "/health"}


def _error(status_code: int, message: str) -> dict[str, Any]:
    try:
        name = HTTPStatus(status_code).phrase.lower().replace(" ", "_")
    except ValueError:
        name = "error"
    return {"error": name, "message": message, "request_id": request_id_var.get()}


def create_app(
    settings: Settings | None = None, simulation: SimulationState | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    logger = configure_logging(settings.log_level)
    simulation = simulation or SimulationState(max_incidents=settings.max_incidents)

    app = FastAPI(
        title="CloudRescue",
        version=__version__,
        description=(
            "Local incident/recovery simulation. **No AWS integration in this phase**; "
            "every incident is simulated and held in memory."
        ),
    )
    app.state.settings = settings
    app.state.simulation = simulation
    app.state.monitoring = MonitoringStore(max_incidents=settings.max_incidents)
    app.state.metrics = Metrics(settings, simulation)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception as exc:  # noqa: BLE001 - never leak internals
                log_event(
                    logger, logging.ERROR, "http.unhandled_exception",
                    error_type=type(exc).__name__, path=request.url.path,
                )  # fmt: skip
                response = JSONResponse(
                    status_code=500, content=_error(500, "An unexpected error occurred")
                )
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            app.state.metrics.record_request(request.method, path, response.status_code, elapsed)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            log_event(
                logger,
                logging.DEBUG if request.url.path in _QUIET else logging.INFO,
                "http.request",
                method=request.method, path=request.url.path,
                status=response.status_code, duration_ms=round(elapsed * 1000, 1),
            )  # fmt: skip
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error(exc.status_code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        body = _error(422, "Invalid request")
        body["details"] = [
            {"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content=body)

    static_dir = Path(__file__).resolve().parent / "static"

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.include_router(router)
    app.include_router(alertmanager_router)
    logger.info("startup", extra={"event": "app.started", "context": settings_summary(settings)})
    return app


def settings_summary(settings: Settings) -> dict[str, Any]:
    """Loggable settings (never the demo token)."""
    return {
        "environment": settings.environment,
        "demo_endpoints_enabled": settings.demo_endpoints_enabled,
        "demo_protected": bool(settings.demo_token),
        "aws_configured": settings.aws_configured,
        "version": __version__,
    }


app = create_app()

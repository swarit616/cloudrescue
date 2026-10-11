"""Prometheus metrics. Simulation metrics are prefixed ``cloudrescue_simulated_``.

Each app instance owns a private registry, so tests can create many apps safely.
"""

from __future__ import annotations

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app import __version__
from app.config import Settings
from app.state import SimulationState


class Metrics:
    def __init__(self, settings: Settings, state: SimulationState) -> None:
        self.registry = CollectorRegistry()
        started = time.time()

        info = Gauge(
            "cloudrescue_info",
            "Build information (value is always 1)",
            ["version", "environment"],
            registry=self.registry,
        )
        info.labels(__version__, settings.environment).set(1)

        Gauge(
            "cloudrescue_uptime_seconds",
            "Seconds since the process started",
            registry=self.registry,
        ).set_function(lambda: time.time() - started)

        Gauge(
            "cloudrescue_simulated_service_up",
            "SIMULATED service state: 1 = healthy, 0 = failed (not a real AWS signal)",
            registry=self.registry,
        ).set_function(lambda: 1.0 if state.healthy else 0.0)

        Gauge(
            "cloudrescue_simulated_incidents_open",
            "Open SIMULATED incidents",
            registry=self.registry,
        ).set_function(lambda: float(state.counts()[1]))

        Gauge(
            "cloudrescue_aws_integration_configured",
            "1 if a future AWS target is described via env vars (no AWS calls are made)",
            registry=self.registry,
        ).set(1 if settings.aws_configured else 0)

        self._failures = Counter(
            "cloudrescue_simulated_failures_total",
            "SIMULATED failures started via the demo endpoint",
            ["severity"],
            registry=self.registry,
        )
        self._recoveries = Counter(
            "cloudrescue_simulated_recoveries_total",
            "SIMULATED recoveries performed via the demo endpoint",
            registry=self.registry,
        )
        self._requests = Counter(
            "cloudrescue_http_requests_total",
            "HTTP requests",
            ["method", "path", "status"],
            registry=self.registry,
        )
        self._latency = Histogram(
            "cloudrescue_http_request_duration_seconds",
            "HTTP request latency",
            ["method", "path"],
            registry=self.registry,
        )

    def record_failure(self, severity: str) -> None:
        self._failures.labels(severity).inc()

    def record_recovery(self) -> None:
        self._recoveries.inc()

    def record_request(self, method: str, path: str, status: int, seconds: float) -> None:
        self._requests.labels(method, path, str(status)).inc()
        self._latency.labels(method, path).observe(seconds)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST

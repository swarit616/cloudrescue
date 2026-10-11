"""The in-memory simulation. Standard library only; no AWS, no I/O.

All state lives in one ``SimulationState`` object. It is lost on restart by design.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

Severity = Literal["low", "medium", "high"]
IncidentStatus = Literal["open", "resolved"]


class InvalidTransition(Exception):
    """The requested transition is not allowed from the current simulated state."""


@dataclass
class Incident:
    id: int
    reason: str
    severity: Severity
    started_at: datetime
    status: IncidentStatus = "open"
    resolved_at: datetime | None = None
    # Always true in this phase: every incident is a local simulation.
    simulated: bool = True
    source: str = "local-simulation"


def utcnow() -> datetime:
    return datetime.now(UTC)


class SimulationState:
    """Thread-safe healthy/failed state machine plus a bounded incident history."""

    def __init__(self, max_incidents: int = 100, clock: Callable[[], datetime] = utcnow) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._max = max_incidents
        self._incidents: list[Incident] = []
        self._next_id = 1
        self._since = clock()

    @property
    def healthy(self) -> bool:
        with self._lock:
            return self._open_locked() is None

    def _open_locked(self) -> Incident | None:
        for incident in reversed(self._incidents):
            if incident.status == "open":
                return incident
        return None

    def current(self) -> tuple[bool, datetime, Incident | None]:
        """(healthy, state-since, open incident or None) as one consistent snapshot."""
        with self._lock:
            return self._open_locked() is None, self._since, self._open_locked()

    def simulate_failure(self, reason: str, severity: Severity) -> Incident:
        with self._lock:
            if self._open_locked() is not None:
                raise InvalidTransition("The simulated service is already failed")
            now = self._clock()
            incident = Incident(id=self._next_id, reason=reason, severity=severity, started_at=now)
            self._next_id += 1
            self._incidents.append(incident)
            if len(self._incidents) > self._max:
                self._incidents = self._incidents[-self._max :]
            self._since = now
            return incident

    def recover(self) -> Incident:
        with self._lock:
            incident = self._open_locked()
            if incident is None:
                raise InvalidTransition("The simulated service is already healthy")
            now = self._clock()
            incident.status = "resolved"
            incident.resolved_at = now
            self._since = now
            return incident

    def incidents(self, status: IncidentStatus | None = None, limit: int = 100) -> list[Incident]:
        """Newest first."""
        with self._lock:
            items = [i for i in reversed(self._incidents) if status in (None, i.status)]
            return items[:limit]

    def counts(self) -> tuple[int, int]:
        """(total incidents ever kept in history, currently open)."""
        with self._lock:
            return len(self._incidents), sum(1 for i in self._incidents if i.status == "open")

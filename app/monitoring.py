"""Thread-safe, bounded in-memory storage for external monitoring alerts."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, TypedDict

AlertStatus = Literal["firing", "resolved"]
IncidentStatus = Literal["open", "resolved"]


class AlertInput(TypedDict):
    fingerprint: str
    alertname: str
    reason: str
    severity: str
    source: str
    status: AlertStatus
    alert_starts_at: datetime | None
    alert_ends_at: datetime | None


@dataclass
class MonitoringIncident:
    fingerprint: str
    alertname: str
    reason: str
    severity: str
    source: str
    started_at: datetime
    alert_starts_at: datetime | None = None
    alert_ends_at: datetime | None = None
    status: IncidentStatus = "open"
    resolved_at: datetime | None = None
    last_received_at: datetime | None = None


class MonitoringStore:
    def __init__(self, max_incidents: int = 100) -> None:
        if max_incidents < 1:
            raise ValueError("max_incidents must be positive")

        self._lock = threading.RLock()
        self._max = max_incidents
        self._incidents: dict[str, MonitoringIncident] = {}

    @staticmethod
    def _validate_timestamp(value: datetime | None) -> None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Alert timestamps must include a timezone")

    def process(
        self,
        *,
        fingerprint: str,
        alertname: str,
        reason: str,
        severity: str,
        source: str,
        status: AlertStatus,
        alert_starts_at: datetime | None = None,
        alert_ends_at: datetime | None = None,
    ) -> MonitoringIncident | None:
        if not fingerprint.strip():
            raise ValueError("Alert fingerprint cannot be empty")

        if status not in ("firing", "resolved"):
            raise ValueError("Invalid alert status")

        self._validate_timestamp(alert_starts_at)
        self._validate_timestamp(alert_ends_at)

        if (
            alert_starts_at is not None
            and alert_ends_at is not None
            and alert_ends_at < alert_starts_at
        ):
            raise ValueError("Alert end time cannot precede its start time")

        now = datetime.now(UTC)

        with self._lock:
            incident = self._incidents.get(fingerprint)

            if status == "resolved":
                if incident is None:
                    return None

                if (
                    alert_starts_at is not None
                    and incident.alert_starts_at is not None
                    and alert_starts_at != incident.alert_starts_at
                ):
                    return replace(incident)

                if incident.status == "open":
                    incident.status = "resolved"
                    incident.resolved_at = now
                    incident.alert_ends_at = alert_ends_at

                incident.last_received_at = now
                return replace(incident)

            if incident is not None:
                if alert_starts_at is not None and incident.alert_starts_at is not None:
                    if alert_starts_at < incident.alert_starts_at:
                        return replace(incident)

                    if alert_starts_at == incident.alert_starts_at:
                        incident.last_received_at = now
                        return replace(incident)

                if incident.status == "resolved":
                    incident.status = "open"
                    incident.started_at = now
                    incident.resolved_at = None
                    incident.alert_ends_at = None
                    incident.alert_starts_at = alert_starts_at
                    incident.alertname = alertname
                    incident.reason = reason
                    incident.severity = severity
                    incident.source = source

                elif alert_starts_at is not None:
                    incident.alert_starts_at = alert_starts_at

                incident.last_received_at = now
                return replace(incident)

            if len(self._incidents) >= self._max:
                resolved = [
                    key for key, item in self._incidents.items() if item.status == "resolved"
                ]

                if not resolved:
                    raise OverflowError("Monitoring incident capacity reached")

                oldest = min(
                    resolved,
                    key=lambda key: self._incidents[key].started_at,
                )
                del self._incidents[oldest]

            incident = MonitoringIncident(
                fingerprint=fingerprint,
                alertname=alertname,
                reason=reason,
                severity=severity,
                source=source,
                started_at=now,
                alert_starts_at=alert_starts_at,
                last_received_at=now,
            )

            self._incidents[fingerprint] = incident
            return replace(incident)

    def process_batch(
        self,
        alerts: list[AlertInput],
    ) -> list[MonitoringIncident | None]:
        """Apply an entire batch atomically, rolling back on failure."""

        with self._lock:
            snapshot = {key: replace(item) for key, item in self._incidents.items()}

            try:
                return [self.process(**alert) for alert in alerts]
            except Exception:
                self._incidents = snapshot
                raise

    def incidents(
        self,
        status: IncidentStatus | None = None,
    ) -> list[MonitoringIncident]:
        with self._lock:
            items = [
                replace(item)
                for item in self._incidents.values()
                if status is None or item.status == status
            ]

        return sorted(
            items,
            key=lambda item: item.started_at,
            reverse=True,
        )

    def counts(self) -> tuple[int, int]:
        with self._lock:
            return (
                len(self._incidents),
                sum(item.status == "open" for item in self._incidents.values()),
            )

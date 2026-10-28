"""Authenticated receiver for Prometheus Alertmanager webhooks."""

from __future__ import annotations

import hmac
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.monitoring import AlertInput

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class IncomingAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["firing", "resolved"]
    fingerprint: str = Field(min_length=1, max_length=256)
    labels: dict[str, str]
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime
    endsAt: datetime | None = None


class AlertmanagerPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str
    status: Literal["firing", "resolved"]
    receiver: str
    alerts: list[IncomingAlert] = Field(min_length=1, max_length=100)


@router.post("/alertmanager")
def receive_alertmanager(
    payload: AlertmanagerPayload,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    """Receive authenticated monitoring notifications."""

    settings = request.app.state.settings
    expected = settings.alertmanager_token

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Integration is disabled",
        )

    scheme, separator, supplied = (authorization or "").partition(" ")

    if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid integration credentials",
        )

    batch: list[AlertInput] = []

    # Validate the complete payload before modifying monitoring state.
    for alert in payload.alerts:
        alertname = alert.labels.get("alertname", "").strip()

        if not alertname:
            raise HTTPException(
                status_code=422,
                detail="Missing alertname",
            )

        for timestamp in (alert.startsAt, alert.endsAt):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Timezone required",
                )

        # Alertmanager may send a zero-value endsAt for firing alerts.
        ends_at = alert.endsAt if alert.status == "resolved" else None

        if ends_at is not None and ends_at < alert.startsAt:
            raise HTTPException(
                status_code=422,
                detail="Invalid alert timestamps",
            )

        batch.append(
            {
                "fingerprint": alert.fingerprint,
                "alertname": alertname,
                "reason": (
                    alert.annotations.get("description")
                    or alert.annotations.get("summary")
                    or alertname
                )[:200],
                "severity": alert.labels.get("severity", "unknown"),
                "source": "cloudops360",
                "status": alert.status,
                "alert_starts_at": alert.startsAt,
                "alert_ends_at": ends_at,
            }
        )

    try:
        request.app.state.monitoring.process_batch(batch)

    except OverflowError as exc:
        raise HTTPException(
            status_code=503,
            detail="Monitoring incident capacity reached",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "accepted": True,
        "processed": len(batch),
        "storage": "in-memory",
        "source": "cloudops360",
    }

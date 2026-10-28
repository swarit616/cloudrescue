"""Tests for the read-only monitoring incidents API."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app


def test_monitoring_incidents_lifecycle():
    app = create_app()
    client = TestClient(app)

    # Initially empty.
    response = client.get("/api/monitoring/incidents")
    assert response.status_code == 200
    assert response.json()["total_count"] == 0
    assert response.json()["incidents"] == []

    started = datetime.now(UTC)

    app.state.monitoring.process(
        fingerprint="test-fingerprint-001",
        alertname="HighCPU",
        reason="CPU utilization exceeded threshold",
        severity="warning",
        source="cloudops360",
        status="firing",
        alert_starts_at=started,
    )

    response = client.get("/api/monitoring/incidents")
    assert response.status_code == 200

    data = response.json()
    assert data["count"] == 1
    assert data["total_count"] == 1
    assert data["open_count"] == 1
    assert data["resolved_count"] == 0
    assert data["storage"] == "in-memory"

    incident = data["incidents"][0]
    assert incident["alertname"] == "HighCPU"
    assert incident["severity"] == "warning"
    assert incident["source"] == "cloudops360"
    assert incident["status"] == "open"

    # Existing simulation endpoint must remain separate.
    assert client.get("/api/incidents").json()["count"] == 0

    app.state.monitoring.process(
        fingerprint="test-fingerprint-001",
        alertname="HighCPU",
        reason="CPU utilization returned to normal",
        severity="warning",
        source="cloudops360",
        status="resolved",
        alert_starts_at=started,
        alert_ends_at=started + timedelta(minutes=2),
    )

    data = client.get("/api/monitoring/incidents").json()
    assert data["open_count"] == 0
    assert data["resolved_count"] == 1
    assert data["incidents"][0]["status"] == "resolved"
    assert data["incidents"][0]["resolved_at"] is not None

    assert client.get("/api/monitoring/incidents?status=open").json()["incidents"] == []

    assert client.get("/api/monitoring/incidents?status=resolved").json()["count"] == 1


def test_monitoring_incidents_query_validation():
    client = TestClient(create_app())

    assert client.get("/api/monitoring/incidents?limit=0").status_code == 422
    assert client.get("/api/monitoring/incidents?limit=101").status_code == 422
    assert client.get("/api/monitoring/incidents?status=invalid").status_code == 422

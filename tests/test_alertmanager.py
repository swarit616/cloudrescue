"""Integration tests for the authenticated Alertmanager receiver."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TOKEN = "integration-test-secret"
START = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)


def payload(status="firing", start=START, fingerprint="alert-001"):
    return {
        "version": "4",
        "receiver": "cloudrescue",
        "status": status,
        "alerts": [
            {
                "status": status,
                "fingerprint": fingerprint,
                "labels": {
                    "alertname": "HostDown",
                    "severity": "critical",
                },
                "annotations": {"description": "Monitoring target unreachable"},
                "startsAt": start.isoformat(),
                "endsAt": (
                    (start + timedelta(minutes=5)).isoformat() if status == "resolved" else None
                ),
            }
        ],
    }


def make_authenticated_client():
    settings = Settings(
        environment="test",
        alertmanager_token=TOKEN,
    )
    return TestClient(create_app(settings))


def send(client, body, token=TOKEN):
    return client.post(
        "/api/integrations/alertmanager",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_integration_disabled_without_secret(client):
    response = client.post(
        "/api/integrations/alertmanager",
        json=payload(),
    )
    assert response.status_code == 503


def test_missing_authentication_is_rejected():
    client = make_authenticated_client()
    response = client.post("/api/integrations/alertmanager", json=payload())
    assert response.status_code == 401
    assert client.app.state.monitoring.counts() == (0, 0)


def test_invalid_token_is_rejected():
    client = make_authenticated_client()
    response = send(client, payload(), token="wrong")
    assert response.status_code == 401
    assert client.app.state.monitoring.counts() == (0, 0)


def test_valid_firing_notification_creates_incident():
    client = make_authenticated_client()
    response = send(client, payload())

    assert response.status_code == 200
    assert response.json()["processed"] == 1
    assert client.app.state.monitoring.counts() == (1, 1)


def test_duplicate_firing_is_deduplicated():
    client = make_authenticated_client()

    assert send(client, payload()).status_code == 200
    assert send(client, payload()).status_code == 200
    assert client.app.state.monitoring.counts() == (1, 1)


def test_resolution_closes_incident():
    client = make_authenticated_client()

    send(client, payload())
    response = send(client, payload(status="resolved"))

    assert response.status_code == 200
    assert client.app.state.monitoring.counts() == (1, 0)


def test_newer_occurrence_reopens_incident():
    client = make_authenticated_client()

    send(client, payload())
    send(client, payload(status="resolved"))

    newer = START + timedelta(hours=1)
    response = send(client, payload(start=newer))

    assert response.status_code == 200
    assert client.app.state.monitoring.counts() == (1, 1)


def test_old_resolution_cannot_close_new_occurrence():
    client = make_authenticated_client()

    send(client, payload())
    send(client, payload(status="resolved"))
    send(client, payload(start=START + timedelta(hours=1)))

    send(client, payload(status="resolved", start=START))

    assert client.app.state.monitoring.counts() == (1, 1)


def test_missing_alertname_rejected_without_mutation():
    client = make_authenticated_client()
    body = payload()
    body["alerts"][0]["labels"] = {}

    response = send(client, body)

    assert response.status_code == 422
    assert client.app.state.monitoring.counts() == (0, 0)


def test_invalid_timestamp_rejected():
    client = make_authenticated_client()
    body = payload()
    body["alerts"][0]["startsAt"] = "not-a-date"

    response = send(client, body)

    assert response.status_code == 422
    assert client.app.state.monitoring.counts() == (0, 0)


def test_invalid_second_alert_rejects_entire_batch():
    client = make_authenticated_client()
    body = payload()

    invalid = payload(fingerprint="alert-002")["alerts"][0]
    invalid["labels"] = {}
    body["alerts"].append(invalid)

    response = send(client, body)

    assert response.status_code == 422
    assert client.app.state.monitoring.counts() == (0, 0)


def test_monitoring_alert_does_not_change_demo_state():
    client = make_authenticated_client()

    response = send(client, payload())

    assert response.status_code == 200
    assert client.app.state.simulation.healthy is True


def test_capacity_failure_rolls_back_entire_batch():
    settings = Settings(
        environment="test",
        alertmanager_token=TOKEN,
        max_incidents=1,
    )
    client = TestClient(create_app(settings))

    body = payload()
    body["alerts"].append(payload(fingerprint="alert-002")["alerts"][0])

    response = send(client, body)

    assert response.status_code == 503
    assert client.app.state.monitoring.counts() == (0, 0)

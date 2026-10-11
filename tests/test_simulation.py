"""Simulated failure/recovery transitions, validation, incident history and demo guards."""

from __future__ import annotations

import pytest


def fail(client, **body):
    return client.post("/api/demo/simulate-failure", json=body or None)


# ------------------------------------------------------------------ transitions


def test_simulate_failure_creates_open_simulated_incident(client):
    response = fail(client, reason="disk full", severity="high")
    assert response.status_code == 201
    body = response.json()
    assert body["simulated"] is True
    assert "does not represent any real AWS" in body["note"]
    incident = body["incident"]
    assert incident["id"] == 1
    assert incident["status"] == "open"
    assert incident["severity"] == "high"
    assert incident["reason"] == "disk full"
    assert incident["simulated"] is True
    assert incident["source"] == "local-simulation"
    assert incident["resolved_at"] is None


def test_simulate_failure_accepts_empty_body_with_defaults(client):
    response = client.post("/api/demo/simulate-failure")
    assert response.status_code == 201
    assert response.json()["incident"]["reason"] == "manual demo failure"
    assert response.json()["incident"]["severity"] == "medium"


def test_simulate_failure_accepts_empty_json_object(client):
    response = client.post("/api/demo/simulate-failure", json={})
    assert response.status_code == 201


def test_recover_resolves_incident_and_restores_healthy_state(client):
    fail(client)
    response = client.post("/api/demo/recover")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Simulated recovery completed"
    assert body["simulated"] is True
    assert body["incident"]["status"] == "resolved"
    assert body["incident"]["resolved_at"] >= body["incident"]["started_at"]
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["simulated_service"]["state"] == "healthy"


def test_failure_twice_is_conflict_and_does_not_add_incident(client):
    assert fail(client).status_code == 201
    second = fail(client)
    assert second.status_code == 409
    assert second.json()["error"] == "conflict"
    assert client.get("/api/incidents").json()["count"] == 1


def test_recover_when_healthy_is_conflict(client):
    response = client.post("/api/demo/recover")
    assert response.status_code == 409
    assert "already healthy" in response.json()["message"]
    assert client.get("/api/status").status_code == 200


def test_full_cycle_can_repeat_with_new_incident_ids(client):
    for expected_id in (1, 2, 3):
        assert fail(client).json()["incident"]["id"] == expected_id
        assert client.post("/api/demo/recover").status_code == 200
    assert client.get("/api/incidents").json()["count"] == 3


# ------------------------------------------------------------------ validation


@pytest.mark.parametrize(
    "payload",
    [
        {"severity": "catastrophic"},
        {"severity": 5},
        {"reason": ""},
        {"reason": "   "},
        {"reason": "x" * 201},
        {"reason": 123},
        {"unexpected": "field"},
    ],
)
def test_simulate_failure_rejects_invalid_input(client, payload):
    response = client.post("/api/demo/simulate-failure", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Invalid request"
    assert body["details"] and {"loc", "msg", "type"} <= set(body["details"][0])
    # An invalid request must not change the simulated state.
    assert client.get("/api/status").status_code == 200


def test_malformed_json_is_rejected(client):
    response = client.post(
        "/api/demo/simulate-failure",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_reason_whitespace_is_trimmed(client):
    incident = fail(client, reason="  padded  ").json()["incident"]
    assert incident["reason"] == "padded"


# ------------------------------------------------------------------ incident history


def test_incidents_empty_initially(client):
    body = client.get("/api/incidents").json()
    assert body["count"] == 0
    assert body["open_count"] == 0
    assert body["incidents"] == []
    assert body["all_simulated"] is True
    assert "does not represent any real AWS" in body["note"]


def test_incidents_are_newest_first_and_marked_simulated(client):
    fail(client, reason="first")
    client.post("/api/demo/recover")
    fail(client, reason="second")
    body = client.get("/api/incidents").json()
    assert [i["reason"] for i in body["incidents"]] == ["second", "first"]
    assert [i["status"] for i in body["incidents"]] == ["open", "resolved"]
    assert body["open_count"] == 1
    assert all(
        i["simulated"] is True and i["source"] == "local-simulation" for i in body["incidents"]
    )


def test_incidents_filter_by_status_and_limit(client):
    for _ in range(3):
        fail(client)
        client.post("/api/demo/recover")
    fail(client)
    assert client.get("/api/incidents?status=open").json()["count"] == 1
    assert client.get("/api/incidents?status=resolved").json()["count"] == 3
    assert client.get("/api/incidents?limit=2").json()["count"] == 2


@pytest.mark.parametrize("query", ["status=bogus", "limit=0", "limit=101", "limit=abc"])
def test_incidents_validate_query_parameters(client, query):
    response = client.get(f"/api/incidents?{query}")
    assert response.status_code == 422
    assert response.json()["details"]


def test_incident_history_is_bounded(make_client):
    client = make_client(max_incidents=3)
    for _ in range(5):
        fail(client)
        client.post("/api/demo/recover")
    incidents = client.get("/api/incidents").json()["incidents"]
    assert [i["id"] for i in incidents] == [5, 4, 3]


# ------------------------------------------------------------------ demo endpoint protection


def test_demo_endpoints_can_be_disabled(make_client):
    client = make_client(demo_endpoints_enabled=False)
    for method, path in (("post", "/api/demo/simulate-failure"), ("post", "/api/demo/recover")):
        response = getattr(client, method)(path)
        assert response.status_code == 403
        assert "disabled" in response.json()["message"]
    # read-only endpoints keep working and nothing changed
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/incidents").json()["count"] == 0


def test_disabled_check_happens_before_body_validation(make_client):
    client = make_client(demo_endpoints_enabled=False)
    response = client.post("/api/demo/simulate-failure", json={"severity": "nope"})
    assert response.status_code == 403


def test_demo_token_is_enforced_when_configured(make_client):
    client = make_client(demo_token="s3cret")
    assert client.post("/api/demo/simulate-failure").status_code == 401
    assert (
        client.post("/api/demo/simulate-failure", headers={"X-Demo-Token": "wrong"}).status_code
        == 401
    )
    ok = client.post("/api/demo/simulate-failure", headers={"X-Demo-Token": "s3cret"})
    assert ok.status_code == 201
    assert client.post("/api/demo/recover").status_code == 401
    assert client.post("/api/demo/recover", headers={"X-Demo-Token": "s3cret"}).status_code == 200


def test_read_endpoints_do_not_need_the_demo_token(make_client):
    client = make_client(demo_token="s3cret")
    for path in ("/", "/health", "/api/status", "/api/incidents", "/metrics"):
        assert client.get(path).status_code == 200, path


def test_demo_token_never_appears_in_responses(make_client):
    client = make_client(demo_token="s3cret-value")
    client.post("/api/demo/simulate-failure", headers={"X-Demo-Token": "s3cret-value"})
    for path in ("/", "/api/status", "/api/incidents", "/metrics", "/openapi.json"):
        assert "s3cret-value" not in client.get(path).text

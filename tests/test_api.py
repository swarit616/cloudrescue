"""Info, health and status endpoints plus generic API behaviour."""

from __future__ import annotations

from datetime import datetime


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_root_describes_project_and_links_to_docs(client):
    response = client.get("/api/info")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "CloudRescue"
    assert body["runtime_mode"] == "local-simulation"
    assert body["docs_url"] == "/docs"
    assert body["openapi_url"] == "/openapi.json"
    assert "POST /api/demo/simulate-failure" in body["endpoints"].values()
    assert "public deployment" in body["warning"]


def test_documentation_links_resolve(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    schema = client.get("/openapi.json").json()
    assert {"/health", "/api/status", "/api/incidents", "/metrics"} <= set(schema["paths"])


def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "cloudrescue"
    assert body["version"]
    assert parse_time(body["timestamp"]).tzinfo is not None


def test_health_is_process_liveness_and_ignores_simulated_failure(client):
    client.post("/api/demo/simulate-failure")
    assert client.get("/health").status_code == 200


def test_status_when_healthy(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "cloudrescue"
    assert body["runtime_mode"] == "local-simulation"
    assert body["environment"] == "test"
    assert body["simulated_service"]["state"] == "healthy"
    assert body["simulated_service"]["simulated"] is True
    assert body["simulated_service"]["open_incident_id"] is None
    assert parse_time(body["timestamp"]).tzinfo is not None
    assert parse_time(body["simulated_service"]["since"]).tzinfo is not None


def test_status_returns_503_with_same_body_shape_when_simulated_failure_active(client):
    client.post("/api/demo/simulate-failure", json={"reason": "db down"})
    response = client.get("/api/status")
    assert response.status_code == 503
    body = response.json()
    assert body["simulated_service"]["state"] == "failed"
    assert body["simulated_service"]["open_incident_id"] == 1
    assert body["aws"]["status"] == "not_checked"


def test_unknown_route_returns_json_error_with_request_id(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert body["request_id"] == response.headers["x-request-id"]


def test_wrong_method_returns_405_json(client):
    response = client.get("/api/demo/simulate-failure")
    assert response.status_code == 405
    assert response.json()["error"] == "method_not_allowed"


def test_request_id_is_generated_echoed_and_sanitised(client):
    assert len(client.get("/health").headers["x-request-id"]) == 32
    assert (
        client.get("/health", headers={"X-Request-ID": "trace-1"}).headers["x-request-id"]
        == "trace-1"
    )
    bad = client.get("/health", headers={"X-Request-ID": "bad id!"})
    assert bad.headers["x-request-id"] != "bad id!"


def test_security_header_present(client):
    assert client.get("/health").headers["x-content-type-options"] == "nosniff"

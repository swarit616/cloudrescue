"""Prometheus metrics."""

from __future__ import annotations

from tests.conftest import sample


def test_metrics_endpoint_is_prometheus_text(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    for name in (
        "cloudrescue_info",
        "cloudrescue_uptime_seconds",
        "cloudrescue_simulated_service_up",
        "cloudrescue_simulated_incidents_open",
        "cloudrescue_aws_integration_configured",
    ):
        assert f"# TYPE {name} gauge" in response.text, name
    assert "# TYPE cloudrescue_simulated_failures_total counter" in response.text
    assert "# TYPE cloudrescue_http_request_duration_seconds histogram" in response.text


def test_metric_names_make_simulation_explicit(client):
    text = client.get("/metrics").text
    assert "cloudrescue_service_up" not in text  # would be ambiguous
    assert "cloudrescue_simulated_service_up" in text


def test_info_metric_has_environment_label(client, metric):
    assert metric("cloudrescue_info", environment="test") == 1.0


def test_simulated_service_up_follows_failure_and_recovery(client, metric):
    assert metric("cloudrescue_simulated_service_up") == 1.0
    client.post("/api/demo/simulate-failure")
    assert metric("cloudrescue_simulated_service_up") == 0.0
    assert metric("cloudrescue_simulated_incidents_open") == 1.0
    client.post("/api/demo/recover")
    assert metric("cloudrescue_simulated_service_up") == 1.0
    assert metric("cloudrescue_simulated_incidents_open") == 0.0


def test_failure_and_recovery_counters(client, metric):
    assert metric("cloudrescue_simulated_recoveries_total") == 0.0
    client.post("/api/demo/simulate-failure", json={"severity": "high"})
    client.post("/api/demo/recover")
    client.post("/api/demo/simulate-failure", json={"severity": "low"})
    assert metric("cloudrescue_simulated_failures_total", severity="high") == 1.0
    assert metric("cloudrescue_simulated_failures_total", severity="low") == 1.0
    assert metric("cloudrescue_simulated_recoveries_total") == 1.0


def test_rejected_transitions_do_not_increment_counters(client, metric):
    client.post("/api/demo/recover")  # 409, already healthy
    client.post("/api/demo/simulate-failure", json={"severity": "bogus"})  # 422
    assert metric("cloudrescue_simulated_recoveries_total") == 0.0
    assert metric("cloudrescue_simulated_failures_total", severity="medium") in (None, 0.0)


def test_http_metrics_use_route_templates(client, metric):
    client.get("/api/status")
    client.get("/api/status")
    client.get("/totally/unknown/path/123")
    assert (
        metric("cloudrescue_http_requests_total", method="GET", path="/api/status", status="200")
        == 2.0
    )
    assert (
        metric("cloudrescue_http_requests_total", method="GET", path="unmatched", status="404")
        == 1.0
    )
    assert (
        metric("cloudrescue_http_request_duration_seconds_count", method="GET", path="/api/status")
        == 2.0
    )


def test_503_status_is_counted(client, metric):
    client.post("/api/demo/simulate-failure")
    client.get("/api/status")
    assert (
        metric("cloudrescue_http_requests_total", method="GET", path="/api/status", status="503")
        == 1.0
    )


def test_each_app_has_its_own_registry(make_client):
    first, second = make_client(), make_client()
    first.post("/api/demo/simulate-failure")
    assert sample(first.get("/metrics").text, "cloudrescue_simulated_service_up") == 0.0
    assert sample(second.get("/metrics").text, "cloudrescue_simulated_service_up") == 1.0

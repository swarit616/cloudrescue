"""Tests for the browser dashboard and its static assets."""


def test_dashboard_serves_html(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CloudRescue | Operations Dashboard" in response.text
    assert "MONITORING + SIMULATION" in response.text
    assert "Live Monitoring" in response.text
    assert "Demo Simulation" in response.text
    assert "/static/style.css" in response.text
    assert "/static/dashboard.js" in response.text


def test_dashboard_static_assets(client):
    css = client.get("/static/style.css")
    javascript = client.get("/static/dashboard.js")

    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert ".stat-card" in css.text

    assert javascript.status_code == 200
    assert "javascript" in javascript.headers["content-type"]
    assert 'getJSON("/api/status", [200, 503])' in javascript.text


def test_project_info_remains_available(client):
    response = client.get("/api/info")

    assert response.status_code == 200
    assert response.json()["name"] == "CloudRescue"
    assert response.json()["runtime_mode"] == "local-simulation"

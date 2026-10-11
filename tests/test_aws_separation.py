"""The local simulation and the (future) AWS configuration must never be mixed up."""

from __future__ import annotations

import pathlib

from tests.conftest import sample

ROOT = pathlib.Path(__file__).resolve().parent.parent


def aws_block(client) -> dict:
    return client.get("/api/status").json()["aws"]


def test_aws_not_configured_by_default(client):
    aws = aws_block(client)
    assert aws["configured"] is False
    assert aws["integration_implemented"] is False
    assert aws["status"] == "not_checked"
    assert aws["region"] is None
    assert "No AWS API calls" in aws["note"]


def test_aws_configured_requires_both_region_and_instance(make_client):
    assert aws_block(make_client(aws_region="eu-west-1"))["configured"] is False
    assert aws_block(make_client(aws_instance_id="i-0123456789abcdef0"))["configured"] is False
    assert (
        aws_block(make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0"))[
            "configured"
        ]
        is True
    )


def test_configuring_aws_does_not_mean_it_is_implemented_or_healthy(make_client):
    aws = aws_block(make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0"))
    assert aws["configured"] is True
    assert aws["integration_implemented"] is False
    assert aws["status"] == "not_checked"
    assert aws["region"] == "eu-west-1"


def test_instance_id_is_not_exposed_by_the_api(make_client):
    client = make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0")
    for path in ("/", "/api/status", "/api/incidents", "/metrics"):
        assert "i-0123456789abcdef0" not in client.get(path).text


def test_aws_configuration_does_not_change_simulated_state(make_client):
    client = make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0")
    body = client.get("/api/status").json()
    assert body["simulated_service"]["state"] == "healthy"
    assert client.get("/api/incidents").json()["count"] == 0


def test_simulated_failure_does_not_change_aws_section(make_client):
    client = make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0")
    before = aws_block(client)
    client.post("/api/demo/simulate-failure")
    assert aws_block(client) == before
    client.post("/api/demo/recover")
    assert aws_block(client) == before


def test_incidents_never_claim_to_be_real_aws_events(make_client):
    client = make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0")
    client.post("/api/demo/simulate-failure")
    incident = client.get("/api/incidents").json()["incidents"][0]
    assert incident["simulated"] is True
    assert incident["source"] == "local-simulation"
    assert "aws" not in incident["source"].lower()


def test_metrics_keep_aws_and_simulation_separate(make_client):
    client = make_client(aws_region="eu-west-1", aws_instance_id="i-0123456789abcdef0")
    client.post("/api/demo/simulate-failure")
    text = client.get("/metrics").text
    assert sample(text, "cloudrescue_aws_integration_configured") == 1.0
    assert sample(text, "cloudrescue_simulated_service_up") == 0.0


def test_no_aws_sdk_is_used_or_required_in_this_phase():
    sources = "\n".join(p.read_text() for p in (ROOT / "app").glob("*.py"))
    for forbidden in ("boto3", "botocore", "aioboto3"):
        assert forbidden not in sources
    requirements = (ROOT / "requirements.txt").read_text().lower()
    assert "boto" not in requirements

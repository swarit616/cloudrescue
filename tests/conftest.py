"""Shared fixtures. Every test gets a brand-new app with fresh in-memory state."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from app.config import Settings
from app.main import create_app


@pytest.fixture
def make_client():
    """Factory: ``make_client(demo_token="x", aws_region="eu-west-1", ...)``."""

    def _make(**overrides) -> TestClient:
        settings = Settings(**{"environment": "test", **overrides})
        return TestClient(create_app(settings))

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def sample(text: str, name: str, **labels: str):
    """Value of one Prometheus sample (independent of label order), or None."""
    for family in text_string_to_metric_families(text):
        for s in family.samples:
            if s.name == name and all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return None


@pytest.fixture
def metric(client):
    """``metric(name, **labels)`` reads the current value from the default client's /metrics."""

    def _read(name: str, **labels: str):
        return sample(client.get("/metrics").text, name, **labels)

    return _read

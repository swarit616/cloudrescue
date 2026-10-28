"""Tests for the external monitoring incident lifecycle."""

from datetime import UTC, datetime, timedelta

import pytest

from app.monitoring import MonitoringStore


def send(
    store,
    fingerprint="alert-001",
    status="firing",
    alert_starts_at=None,
    alert_ends_at=None,
):
    return store.process(
        fingerprint=fingerprint,
        alertname="HostDown",
        reason="CloudOps360 monitoring target is unreachable",
        severity="critical",
        source="cloudops360",
        status=status,
        alert_starts_at=alert_starts_at,
        alert_ends_at=alert_ends_at,
    )


def test_firing_creates_incident():
    store = MonitoringStore()

    incident = send(store)

    assert incident is not None
    assert incident.status == "open"
    assert incident.fingerprint == "alert-001"
    assert incident.source == "cloudops360"
    assert store.counts() == (1, 1)


def test_duplicate_firing_does_not_create_another_incident():
    store = MonitoringStore()

    first = send(store)
    second = send(store)

    assert first is not None
    assert second is not None
    assert first.fingerprint == second.fingerprint
    assert first.started_at == second.started_at
    assert store.counts() == (1, 1)
    assert len(store.incidents()) == 1


def test_resolved_notification_closes_incident():
    store = MonitoringStore()

    send(store)
    incident = send(store, status="resolved")

    assert incident is not None
    assert incident.status == "resolved"
    assert incident.resolved_at is not None
    assert store.counts() == (1, 0)


def test_duplicate_resolution_is_idempotent():
    store = MonitoringStore()

    send(store)
    first = send(store, status="resolved")

    assert first is not None
    original_resolution_time = first.resolved_at

    second = send(store, status="resolved")

    assert second is not None
    assert second.resolved_at == original_resolution_time
    assert store.counts() == (1, 0)


def test_unknown_resolution_does_not_create_incident():
    store = MonitoringStore()

    result = send(store, status="resolved")

    assert result is None
    assert store.counts() == (0, 0)


def test_resolved_incident_can_fire_again():
    store = MonitoringStore()

    send(store)
    send(store, status="resolved")

    incident = send(store, status="firing")

    assert incident is not None
    assert incident.status == "open"
    assert incident.resolved_at is None
    assert store.counts() == (1, 1)


def test_different_fingerprints_create_separate_incidents():
    store = MonitoringStore()

    send(store, fingerprint="alert-001")
    send(store, fingerprint="alert-002")

    assert store.counts() == (2, 2)


def test_capacity_never_silently_discards_open_incidents():
    store = MonitoringStore(max_incidents=1)

    send(store, fingerprint="alert-001")

    with pytest.raises(OverflowError):
        send(store, fingerprint="alert-002")

    assert store.counts() == (1, 1)


def test_resolved_incident_can_be_evicted_when_capacity_is_reached():
    store = MonitoringStore(max_incidents=1)

    send(store, fingerprint="alert-001")
    send(store, fingerprint="alert-001", status="resolved")
    send(store, fingerprint="alert-002")

    assert store.counts() == (1, 1)
    assert store.incidents()[0].fingerprint == "alert-002"


def test_incidents_returns_snapshot_not_internal_objects():
    store = MonitoringStore()

    send(store)
    snapshot = store.incidents()
    snapshot[0].reason = "Modified externally"

    assert store.incidents()[0].reason != "Modified externally"


def test_monitoring_does_not_change_demo_simulation(client):
    """External monitoring state must remain independent of demo state."""
    monitoring = MonitoringStore()
    send(monitoring)

    response = client.get("/api/status")

    assert response.status_code == 200
    assert client.app.state.simulation.healthy is True
    assert monitoring.counts() == (1, 1)


# ---------------------------------------------------------
# Alertmanager timestamp and lifecycle tests
# ---------------------------------------------------------


def test_alertmanager_start_timestamp_is_stored():
    store = MonitoringStore()
    started = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)

    incident = send(store, alert_starts_at=started)

    assert incident is not None
    assert incident.alert_starts_at == started


def test_duplicate_firing_with_same_timestamp_does_not_reopen():
    store = MonitoringStore()
    started = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)

    send(store, alert_starts_at=started)
    send(store, status="resolved", alert_starts_at=started)

    incident = send(store, alert_starts_at=started)

    assert incident is not None
    assert incident.status == "resolved"
    assert store.counts() == (1, 0)


def test_newer_alert_occurrence_reopens_resolved_incident():
    store = MonitoringStore()
    first_start = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    second_start = first_start + timedelta(minutes=30)

    send(store, alert_starts_at=first_start)
    send(store, status="resolved", alert_starts_at=first_start)

    incident = send(store, alert_starts_at=second_start)

    assert incident is not None
    assert incident.status == "open"
    assert incident.alert_starts_at == second_start
    assert incident.resolved_at is None
    assert store.counts() == (1, 1)


def test_old_firing_cannot_replace_newer_occurrence():
    store = MonitoringStore()
    first_start = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    second_start = first_start + timedelta(minutes=30)

    send(store, alert_starts_at=first_start)
    send(store, status="resolved", alert_starts_at=first_start)
    send(store, alert_starts_at=second_start)

    incident = send(store, alert_starts_at=first_start)

    assert incident is not None
    assert incident.status == "open"
    assert incident.alert_starts_at == second_start
    assert store.counts() == (1, 1)


def test_old_resolution_cannot_close_newer_occurrence():
    store = MonitoringStore()
    first_start = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    second_start = first_start + timedelta(minutes=30)

    send(store, alert_starts_at=first_start)
    send(store, status="resolved", alert_starts_at=first_start)
    send(store, alert_starts_at=second_start)

    incident = send(
        store,
        status="resolved",
        alert_starts_at=first_start,
        alert_ends_at=first_start + timedelta(minutes=10),
    )

    assert incident is not None
    assert incident.status == "open"
    assert incident.alert_starts_at == second_start
    assert store.counts() == (1, 1)


def test_resolution_stores_alertmanager_end_timestamp():
    store = MonitoringStore()
    started = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)
    ended = started + timedelta(minutes=5)

    send(store, alert_starts_at=started)

    incident = send(
        store,
        status="resolved",
        alert_starts_at=started,
        alert_ends_at=ended,
    )

    assert incident is not None
    assert incident.status == "resolved"
    assert incident.alert_ends_at == ended


def test_naive_timestamp_is_rejected():
    store = MonitoringStore()
    naive = datetime(2026, 10, 28, 10, 0)

    with pytest.raises(ValueError, match="timezone"):
        send(store, alert_starts_at=naive)

    assert store.counts() == (0, 0)


def test_end_before_start_is_rejected():
    store = MonitoringStore()
    started = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="precede"):
        send(
            store,
            alert_starts_at=started,
            alert_ends_at=started - timedelta(minutes=1),
        )

    assert store.counts() == (0, 0)


def test_empty_fingerprint_is_rejected():
    store = MonitoringStore()

    with pytest.raises(ValueError, match="fingerprint"):
        send(store, fingerprint=" ")

    assert store.counts() == (0, 0)


def test_invalid_capacity_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        MonitoringStore(max_incidents=0)

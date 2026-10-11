"""The simulation state machine on its own (standard library only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.state import InvalidTransition, SimulationState


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


def test_starts_healthy_with_no_incidents():
    state = SimulationState()
    assert state.healthy is True
    assert state.incidents() == []
    assert state.counts() == (0, 0)


def test_failure_then_recovery_transitions():
    clock = FakeClock()
    state = SimulationState(clock=clock)
    incident = state.simulate_failure("boom", "high")
    assert (incident.id, incident.status, incident.simulated) == (1, "open", True)
    assert state.healthy is False
    healthy, _since, open_incident = state.current()
    assert healthy is False and open_incident is incident

    resolved = state.recover()
    assert resolved is incident
    assert resolved.status == "resolved"
    assert resolved.resolved_at > resolved.started_at
    assert state.healthy is True


def test_invalid_transitions_raise_and_change_nothing():
    state = SimulationState()
    with pytest.raises(InvalidTransition):
        state.recover()
    state.simulate_failure("a", "low")
    with pytest.raises(InvalidTransition):
        state.simulate_failure("b", "low")
    assert state.counts() == (1, 1)


def test_history_is_newest_first_filterable_and_bounded():
    state = SimulationState(max_incidents=3)
    for index in range(5):
        state.simulate_failure(f"r{index}", "medium")
        state.recover()
    state.simulate_failure("open-one", "medium")
    ids = [i.id for i in state.incidents()]
    assert ids == [6, 5, 4]
    assert [i.id for i in state.incidents(status="open")] == [6]
    assert [i.id for i in state.incidents(status="resolved", limit=1)] == [5]


def test_since_tracks_last_transition():
    clock = FakeClock()
    state = SimulationState(clock=clock)
    _healthy, initial, _ = state.current()
    state.simulate_failure("x", "low")
    _healthy, failed_since, _ = state.current()
    state.recover()
    _healthy, recovered_since, _ = state.current()
    assert initial < failed_since < recovered_since

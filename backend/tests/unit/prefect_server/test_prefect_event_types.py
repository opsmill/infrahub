from __future__ import annotations

import inspect

from prefect import states as client_states
from prefect.server.schemas import states as server_states

from infrahub.prefect_server.retention import PREFECT_EVENT_TYPES


def _state_names_defined_by_prefect() -> set[str]:
    names: set[str] = set()
    for module in (client_states, server_states):
        states = [module.State(type=state_type) for state_type in module.StateType]
        states.extend(
            constructor()
            for name, constructor in inspect.getmembers(module, inspect.isfunction)
            if constructor.__module__ == module.__name__ and name[0].isupper()
        )
        names.update(state.name for state in states if state.name is not None)
    return names


def test_every_built_in_prefect_state_has_its_run_events_listed() -> None:
    """Every state name Prefect defines has its flow-run and task-run event in the list of Prefect event types."""
    state_names = _state_names_defined_by_prefect()

    # One name from a state type and one from a named constructor, so a reader that finds nothing cannot pass.
    assert {"Completed", "AwaitingRetry"} <= state_names
    assert (
        sorted(
            event_type
            for name in state_names
            for event_type in (f"prefect.flow-run.{name}", f"prefect.task-run.{name}")
            if event_type not in PREFECT_EVENT_TYPES
        )
        == []
    )

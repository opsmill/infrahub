from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import prefect
from prefect import states as client_states
from prefect.server.events.schemas.automations import TriggerState
from prefect.server.schemas import states as server_states
from prefect.server.schemas.statuses import DeploymentStatus, WorkPoolStatus, WorkQueueStatus

from infrahub.prefect_server.retention import PREFECT_EVENT_TYPES, unlisted_prefect_event_types

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

_STATE_MODULES = (client_states, server_states)


@dataclass(frozen=True)
class _PrefectSourceNames:
    event_names: frozenset[str]
    event_name_patterns: frozenset[str]
    """Event names built from f-strings, with each placeholder written as `{}`."""
    state_names: frozenset[str]
    lifecycle_kinds: frozenset[str]
    """Kinds of record that Prefect sends created, updated and deleted events for."""


def _state_constructors(
    module: ModuleType,
) -> list[tuple[str, Callable[[], client_states.State | server_states.State]]]:
    return [
        (name, constructor)
        for name, constructor in inspect.getmembers(module, inspect.isfunction)
        if constructor.__module__ == module.__name__ and name[0].isupper()
    ]


def _callee_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _keyword_values(call: ast.Call, *names: str) -> list[ast.expr]:
    return [keyword.value for keyword in call.keywords if keyword.arg in names]


def _is_state_name_attribute(target: ast.expr) -> bool:
    return isinstance(target, ast.Attribute) and target.attr == "name" and "state" in ast.unparse(target.value).lower()


def _string_literals(expressions: list[ast.expr]) -> frozenset[str]:
    return frozenset(
        expression.value
        for expression in expressions
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str)
    )


def _f_string_patterns(expressions: list[ast.expr]) -> frozenset[str]:
    return frozenset(
        "".join(str(part.value) if isinstance(part, ast.Constant) else "{}" for part in expression.values)
        for expression in expressions
        if isinstance(expression, ast.JoinedStr)
    )


@cache
def _names_in_prefect_source() -> _PrefectSourceNames:
    """Read the event names and name patterns, state names and lifecycle event kinds written in Prefect's source."""
    state_constructors = {"State", *(name for module in _STATE_MODULES for name, _ in _state_constructors(module))}
    events: list[ast.expr] = []
    state_names: list[ast.expr] = []
    lifecycle_kinds: list[ast.expr] = []
    for path in Path(prefect.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Assign):
                state_names.extend(node.value for target in node.targets if _is_state_name_attribute(target))
                continue
            if not isinstance(node, ast.Call):
                continue
            callee = _callee_name(node)
            events.extend(_keyword_values(node, "event", "event_type"))
            if callee == "emit_event":
                events.extend(node.args[:1])
            if callee in state_constructors:
                state_names.extend(_keyword_values(node, "name"))
            if callee == "rename_state":
                state_names.extend(node.args[:1])
            if callee == "_lifecycle_event":
                lifecycle_kinds.extend(_keyword_values(node, "kind"))
    return _PrefectSourceNames(
        event_names=_string_literals(events),
        event_name_patterns=_f_string_patterns(events),
        state_names=_string_literals(state_names),
        lifecycle_kinds=_string_literals(lifecycle_kinds),
    )


def test_every_prefect_event_name_in_prefect_source_is_listed() -> None:
    """Every `prefect.*` event name that Prefect's source sends as a literal is in the list of Prefect event types."""
    event_names = _names_in_prefect_source().event_names

    # Two names sent from different parts of Prefect, so a reader that finds nothing cannot pass.
    assert {"prefect.flow-run.heartbeat", "prefect.worker.started"} <= event_names
    assert sorted(name for name in event_names if name.startswith("prefect.") and name not in PREFECT_EVENT_TYPES) == []


def test_prefect_builds_event_names_from_known_patterns_only() -> None:
    """Prefect's source builds event names from these patterns only.

    A new pattern fails this test until its names are listed and the pattern is added here. The other tests do not read
    the lifecycle actions, concurrency limit phases or asset materialization statuses put into these patterns.
    """
    assert _names_in_prefect_source().event_name_patterns == {
        "prefect.flow-run.{}",
        "prefect.task-run.{}",
        "prefect.deployment.{}",
        "prefect.work-pool.{}",
        "prefect.work-queue.{}",
        "prefect.automation.{}",
        "prefect.concurrency-limit.{}",
        "prefect.concurrency-limit.v1.{}",
        "prefect.asset.materialization.{}",
        "prefect.{}.{}",
        "{}.loaded",
    }


def test_every_prefect_status_and_trigger_state_has_its_event_listed() -> None:
    """Every deployment, work pool and work queue status and every automation trigger state has its event listed."""
    event_types = {
        *(f"prefect.deployment.{status.in_kebab_case()}" for status in DeploymentStatus),
        *(f"prefect.work-pool.{status.in_kebab_case()}" for status in WorkPoolStatus),
        *(f"prefect.work-queue.{status.in_kebab_case()}" for status in WorkQueueStatus),
        *(f"prefect.automation.{state.value.lower()}" for state in TriggerState),
    }

    assert sorted(event_types - set(PREFECT_EVENT_TYPES)) == []


def test_every_prefect_lifecycle_event_is_listed() -> None:
    """Every kind of record that Prefect's source sends lifecycle events for has its lifecycle events listed."""
    kinds = _names_in_prefect_source().lifecycle_kinds

    # Two kinds of record, so a reader that finds nothing cannot pass.
    assert {"flow", "automation"} <= kinds
    assert (
        sorted(
            event_type
            for kind in kinds
            for event_type in (f"prefect.{kind}.created", f"prefect.{kind}.updated", f"prefect.{kind}.deleted")
            if event_type not in PREFECT_EVENT_TYPES
        )
        == []
    )


def _state_names_defined_by_prefect() -> set[str]:
    names: set[str] = set()
    for module in _STATE_MODULES:
        states = [module.State(type=state_type) for state_type in module.StateType]
        states.extend(constructor() for _, constructor in _state_constructors(module))
        names.update(state.name for state in states if state.name is not None)
    return names


def test_every_built_in_prefect_state_has_its_run_events_listed() -> None:
    """Every state name Prefect defines or sets in its source has its flow-run and task-run event listed."""
    state_names = _state_names_defined_by_prefect() | _names_in_prefect_source().state_names

    # A name from a state type, one from a named constructor and two that Prefect's source sets on a state, so a
    # reader that finds nothing cannot pass.
    assert {"Completed", "AwaitingRetry", "Cached", "TimedOut"} <= state_names
    assert (
        sorted(
            event_type
            for name in state_names
            for event_type in (f"prefect.flow-run.{name}", f"prefect.task-run.{name}")
            if event_type not in PREFECT_EVENT_TYPES
        )
        == []
    )


def test_only_prefect_event_types_missing_from_the_list_are_unlisted() -> None:
    event_types = [
        "prefect.flow-run.Completed",
        "prefect.work-pool.new-status",
        "prefect.work-pool.new-status",
        "prefect.automation.new-action",
        "infrahub.node.created",
        "custom.prefect.flow-run.Completed",
    ]

    assert unlisted_prefect_event_types(event_types) == [
        "prefect.automation.new-action",
        "prefect.work-pool.new-status",
    ]

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.registry import registry
from infrahub.core.schema.manager import SchemaManager
from infrahub.execution_priority import bind_execution_priority
from infrahub.workers.dependencies import build_client
from infrahub.workflows.constants import WorkflowPriority


@dataclass
class ClientPriorityCase:
    name: str
    priority: WorkflowPriority | None
    environment_priority: str | None
    expected_header: str | None


CLIENT_PRIORITY_CASES = [
    ClientPriorityCase(
        name="low_priority_run", priority=WorkflowPriority.LOW, environment_priority=None, expected_header="low"
    ),
    ClientPriorityCase(
        name="high_priority_run", priority=WorkflowPriority.HIGH, environment_priority=None, expected_header="high"
    ),
    ClientPriorityCase(
        name="outside_of_a_request_or_workflow", priority=None, environment_priority=None, expected_header=None
    ),
    ClientPriorityCase(
        name="run_priority_replaces_the_environment_default",
        priority=WorkflowPriority.HIGH,
        environment_priority="low",
        expected_header="high",
    ),
    ClientPriorityCase(
        name="environment_default_outside_of_a_request_or_workflow",
        priority=None,
        environment_priority="low",
        expected_header="low",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CLIENT_PRIORITY_CASES])
def test_client_sends_the_priority_of_the_run_that_built_it(
    case: ClientPriorityCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The client copies the schemas held by the registry, which a unit test does not load.
    monkeypatch.setattr(registry, "_schema", SchemaManager())
    if case.environment_priority is None:
        monkeypatch.delenv("INFRAHUB_PRIORITY", raising=False)
    else:
        monkeypatch.setenv("INFRAHUB_PRIORITY", case.environment_priority)

    with bind_execution_priority(case.priority):
        client = build_client()

    assert client.headers.get("X-Priority") == case.expected_header

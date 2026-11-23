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
    expected_header: str | None


CLIENT_PRIORITY_CASES = [
    ClientPriorityCase(name="low_priority_run", priority=WorkflowPriority.LOW, expected_header="low"),
    ClientPriorityCase(name="high_priority_run", priority=WorkflowPriority.HIGH, expected_header="high"),
    ClientPriorityCase(name="outside_of_a_request_or_workflow", priority=None, expected_header=None),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CLIENT_PRIORITY_CASES])
def test_client_sends_the_priority_of_the_run_that_built_it(
    case: ClientPriorityCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The client copies the schemas held by the registry, which a unit test does not load.
    monkeypatch.setattr(registry, "_schema", SchemaManager())

    with bind_execution_priority(case.priority):
        client = build_client()

    assert client.headers.get("X-Priority") == case.expected_header

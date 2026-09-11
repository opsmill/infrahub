from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Generator

import pytest

from infrahub.computed_attribute import tasks
from infrahub.computed_attribute.tasks import (
    _partition_transform_results,
    process_transform,
    trigger_update_python_computed_attributes,
)
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.recompute.bulk_write import AttributeValueWrite
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.events.models import EventBranchContext, EventContext
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode

LOGGER_NAME = "infrahub.computed_attribute.tasks"
BRANCH = "main"
CAR_KIND = "TestingCar"
ATTRIBUTE_NAME = "description"
TRANSFORM_NAME = "transform_a"

# The shape the API answers with when no transform matches the filter.
NO_TRANSFORM_FOUND: dict[str, Any] = {"CoreTransformPython": {"edges": []}}


def _write(node_id: str, value: Any) -> AttributeValueWrite:
    return AttributeValueWrite(node_id=node_id, field="desc", value=value)


def test_partition_transform_results_persists_only_string_values() -> None:
    """A string value is persisted; a None or non-string value is skipped so the prior value stays."""
    ok = _write("n1", "hello")
    null_value = _write("n2", None)
    wrong_type = _write("n3", 42)

    writes, skipped = _partition_transform_results([("n1", ok), ("n2", null_value), ("n3", wrong_type)])

    assert writes == [ok]
    reasons = dict(skipped)
    assert list(reasons) == ["n2", "n3"]
    assert "NoneType" in reasons["n2"]
    assert "int" in reasons["n3"]


def test_partition_transform_results_isolates_a_failed_node() -> None:
    """A node whose transform raised is skipped without dropping the healthy nodes' writes."""
    ok1 = _write("n1", "a")
    ok2 = _write("n3", "b")

    writes, skipped = _partition_transform_results([("n1", ok1), ("n2", RuntimeError("boom")), ("n3", ok2)])

    assert writes == [ok1, ok2]
    assert len(skipped) == 1
    assert skipped[0][0] == "n2"
    assert "boom" in skipped[0][1]


def test_partition_transform_results_handles_empty() -> None:
    assert _partition_transform_results([]) == ([], [])


class _RecordingClient:
    """An SDK client stand-in that answers the transform fetch and records every kind it lists."""

    def __init__(self, transform_response: dict[str, Any]) -> None:
        self._transform_response = transform_response
        self.request_context: Any = None
        self.fetched_branches: list[str] = []
        self.listed_kinds: list[str] = []

    async def execute_graphql(self, query: str, variables: dict[str, Any], branch_name: str) -> dict[str, Any]:
        self.fetched_branches.append(branch_name)
        return self._transform_response

    async def all(self, kind: str, branch: str) -> list[InfrahubNode]:
        self.listed_kinds.append(kind)
        return []


@pytest.fixture
def schema_branch_with_a_python_attribute() -> Generator[None, None, None]:
    """Register a schema branch whose car description is fed by a Python transform.

    The registry schema is swapped for a fresh manager so the test never leaks state.
    """
    original = registry._schema
    manager = SchemaManager()
    branch = SchemaBranch(cache={}, name=BRANCH)
    branch.computed_attributes.add_python_attribute(
        node=NodeSchema(name="Car", namespace="Testing"),
        attribute=AttributeSchema(
            name=ATTRIBUTE_NAME,
            kind="Text",
            optional=True,
            computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform=TRANSFORM_NAME),
        ),
    )
    manager.set_schema_branch(name=BRANCH, schema=branch)
    registry.schema = manager
    yield
    registry._schema = original


@pytest.fixture
def client_without_the_transform(monkeypatch: pytest.MonkeyPatch) -> _RecordingClient:
    """Answer the transform fetch with an empty result, as a branch holding no such transform does."""
    client = _RecordingClient(NO_TRANSFORM_FOUND)
    monkeypatch.setattr(tasks, "get_client", lambda: client)
    return client


@pytest.fixture
def recorded_submissions(monkeypatch: pytest.MonkeyPatch) -> WorkflowRecorder:
    recorder = WorkflowRecorder()
    monkeypatch.setattr(tasks, "get_workflow", lambda: recorder)
    return recorder


@pytest.fixture(autouse=True)
def _flow_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the two Prefect runtime calls the flows make outside their own logic."""

    async def _noop(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(tasks, "get_run_logger", lambda: logging.getLogger(LOGGER_NAME))
    monkeypatch.setattr(tasks, "add_tags", _noop)


def _context() -> EventContext:
    return EventContext(branch=EventBranchContext(name=BRANCH), account_id="")


def _missing_transform_warning(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.message for record in caplog.records if record.levelno == logging.WARNING]


async def test_the_fan_out_skips_a_missing_transform_on_a_coalesced_pass(
    schema_branch_with_a_python_attribute: None,
    client_without_the_transform: _RecordingClient,
    recorded_submissions: WorkflowRecorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A widened pass warns and stops before it lists the kind, so no chunk is ever submitted."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await trigger_update_python_computed_attributes.fn(
            branch_name=BRANCH,
            computed_attribute_name=ATTRIBUTE_NAME,
            computed_attribute_kind=CAR_KIND,
            context=_context(),
            coalesced=True,
        )

    assert client_without_the_transform.listed_kinds == []
    assert recorded_submissions.submit_calls == []
    assert _missing_transform_warning(caplog) == [
        f"Skipping the coalesced recompute of '{ATTRIBUTE_NAME}' on branch '{BRANCH}': "
        f"transform '{TRANSFORM_NAME}' is not in the database, so nothing can compute the attribute yet"
    ]


async def test_the_fan_out_raises_on_a_missing_transform_on_the_live_path(
    schema_branch_with_a_python_attribute: None,
    client_without_the_transform: _RecordingClient,
    recorded_submissions: WorkflowRecorder,
) -> None:
    """A live run fails once, in the flow that starts the work, instead of once per chunk."""
    with pytest.raises(
        ValueError,
        match=rf"^Unable to fetch transform '{TRANSFORM_NAME}' for computed attribute '{ATTRIBUTE_NAME}'$",
    ):
        await trigger_update_python_computed_attributes.fn(
            branch_name=BRANCH,
            computed_attribute_name=ATTRIBUTE_NAME,
            computed_attribute_kind=CAR_KIND,
            context=_context(),
            coalesced=False,
        )

    assert client_without_the_transform.listed_kinds == []
    assert recorded_submissions.submit_calls == []


async def test_the_batch_run_skips_a_missing_transform_on_a_coalesced_pass(
    schema_branch_with_a_python_attribute: None,
    client_without_the_transform: _RecordingClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A transform deleted between the widening and the run warns instead of failing the flow."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await process_transform.fn(
            branch_name=BRANCH,
            node_kind=CAR_KIND,
            computed_attribute_name=ATTRIBUTE_NAME,
            computed_attribute_kind=CAR_KIND,
            context=_context(),
            object_ids=["c1", "c2"],
            coalesced=True,
        )

    assert client_without_the_transform.fetched_branches == [BRANCH]
    assert _missing_transform_warning(caplog) == [
        f"Skipping the coalesced recompute of '{ATTRIBUTE_NAME}' on branch '{BRANCH}': "
        f"transform '{TRANSFORM_NAME}' is not in the database, so nothing can compute the attribute yet"
    ]


async def test_the_batch_run_raises_on_a_missing_transform_on_the_live_path(
    schema_branch_with_a_python_attribute: None,
    client_without_the_transform: _RecordingClient,
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"^Unable to fetch transform '{TRANSFORM_NAME}' for computed attribute '{ATTRIBUTE_NAME}'$",
    ):
        await process_transform.fn(
            branch_name=BRANCH,
            node_kind=CAR_KIND,
            computed_attribute_name=ATTRIBUTE_NAME,
            computed_attribute_kind=CAR_KIND,
            context=_context(),
            object_ids=["c1", "c2"],
            coalesced=False,
        )

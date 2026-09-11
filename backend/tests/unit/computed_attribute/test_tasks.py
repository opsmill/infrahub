from __future__ import annotations

import logging
from dataclasses import dataclass
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

UNCONFIGURED_ATTRIBUTE = "no_transform_named"

# The shape the API answers with when no transform matches the filter.
NO_TRANSFORM_FOUND: dict[str, Any] = {"CoreTransformPython": {"edges": []}}

# A transform that is in the database but lost its repository peer. It is not absent, so no run may
# treat it as a state to wait out.
TRANSFORM_WITHOUT_A_REPOSITORY: dict[str, Any] = {
    "CoreTransformPython": {
        "edges": [
            {
                "node": {
                    "id": "txfm-001",
                    "file_path": {"value": "transforms/t.py"},
                    "class_name": {"value": "T"},
                    "timeout": {"value": 60},
                    "convert_query_response": {"value": False},
                    "repository": {"node": None},
                    "query": {"node": {"id": "query-001", "name": {"value": "q"}}},
                }
            }
        ]
    }
}

UNUSABLE_TRANSFORM_ERROR = (
    r"^Transform 'txfm-001' is in the database without the repository, query or file details a run needs$"
)


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


@dataclass
class _RaisingCase:
    """A (coalesced, widened) pair that must still raise on an absent transform."""

    name: str
    coalesced: bool
    widened: bool


def _python_attribute(name: str, transform: str | None) -> AttributeSchema:
    return AttributeSchema(
        name=name,
        kind="Text",
        optional=True,
        computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform=transform),
    )


@pytest.fixture
def schema_branch_with_python_attributes() -> Generator[None, None, None]:
    """Register a schema branch holding one attribute with a transform and one without.

    The registry schema is swapped for a fresh manager so the test never leaks state.
    """
    original = registry._schema
    manager = SchemaManager()
    branch = SchemaBranch(cache={}, name=BRANCH)
    car = NodeSchema(name="Car", namespace="Testing")
    branch.computed_attributes.add_python_attribute(
        node=car, attribute=_python_attribute(ATTRIBUTE_NAME, TRANSFORM_NAME)
    )
    # The schema validator only rejects a mandatory Python attribute, so an unset transform reaches
    # the widened set the same way a named one does.
    branch.computed_attributes.add_python_attribute(node=car, attribute=_python_attribute(UNCONFIGURED_ATTRIBUTE, None))
    manager.set_schema_branch(name=BRANCH, schema=branch)
    registry.schema = manager
    yield
    registry._schema = original


@pytest.fixture
def schema_branch_without_the_attribute() -> Generator[None, None, None]:
    """A registry that does not carry the branch, as a worker behind on the schema has."""
    original = registry._schema
    registry.schema = SchemaManager()
    yield
    registry._schema = original


@pytest.fixture
def client_without_the_transform(monkeypatch: pytest.MonkeyPatch) -> _RecordingClient:
    """Answer the transform fetch with an empty result, as a branch holding no such transform does."""
    client = _RecordingClient(NO_TRANSFORM_FOUND)
    monkeypatch.setattr(tasks, "get_client", lambda: client)
    return client


@pytest.fixture
def client_with_an_unusable_transform(monkeypatch: pytest.MonkeyPatch) -> _RecordingClient:
    client = _RecordingClient(TRANSFORM_WITHOUT_A_REPOSITORY)
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


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.message for record in caplog.records if record.levelno == logging.WARNING and record.name == LOGGER_NAME
    ]


async def _fan_out(*, attribute_name: str = ATTRIBUTE_NAME, widened: bool, coalesced: bool = True) -> None:
    await trigger_update_python_computed_attributes.fn(
        branch_name=BRANCH,
        computed_attribute_name=attribute_name,
        computed_attribute_kind=CAR_KIND,
        context=_context(),
        coalesced=coalesced,
        widened=widened,
    )


async def _batch(*, coalesced: bool, widened: bool) -> None:
    await process_transform.fn(
        branch_name=BRANCH,
        node_kind=CAR_KIND,
        computed_attribute_name=ATTRIBUTE_NAME,
        computed_attribute_kind=CAR_KIND,
        context=_context(),
        object_ids=["c1", "c2"],
        coalesced=coalesced,
        widened=widened,
    )


async def test_a_widened_fan_out_skips_an_absent_transform(
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
    recorded_submissions: WorkflowRecorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A widened run warns and stops before it lists the kind, so no chunk is ever submitted."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await _fan_out(widened=True)

    assert client_without_the_transform.listed_kinds == []
    assert recorded_submissions.submit_calls == []
    assert _warnings(caplog) == [
        f"Skipping the widened recompute of '{ATTRIBUTE_NAME}' on branch '{BRANCH}': "
        f"transform '{TRANSFORM_NAME}' is not in the database, so nothing can compute the attribute yet"
    ]


async def test_a_widened_fan_out_skips_an_attribute_that_names_no_transform(
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
    recorded_submissions: WorkflowRecorder,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The widened set is built from the schema, which can name an attribute with no transform."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await _fan_out(attribute_name=UNCONFIGURED_ATTRIBUTE, widened=True)

    assert client_without_the_transform.fetched_branches == []
    assert client_without_the_transform.listed_kinds == []
    assert recorded_submissions.submit_calls == []
    assert _warnings(caplog) == [
        f"Skipping the widened recompute of '{UNCONFIGURED_ATTRIBUTE}' on branch '{BRANCH}': "
        f"no transform is configured for it, so nothing can compute the attribute yet"
    ]


async def test_a_widened_fan_out_raises_for_a_transform_it_cannot_run(
    schema_branch_with_python_attributes: None,
    client_with_an_unusable_transform: _RecordingClient,
    recorded_submissions: WorkflowRecorder,
) -> None:
    """A transform that is present but broken is a fault, not a state to wait out."""
    with pytest.raises(ValueError, match=UNUSABLE_TRANSFORM_ERROR):
        await _fan_out(widened=True)

    assert client_with_an_unusable_transform.listed_kinds == []
    assert recorded_submissions.submit_calls == []


async def test_a_widened_fan_out_proceeds_when_the_branch_schema_has_no_such_attribute(
    schema_branch_without_the_attribute: None,
    client_without_the_transform: _RecordingClient,
) -> None:
    """A worker whose registry does not carry the branch reports no attribute, and must not skip."""
    await _fan_out(widened=True)

    assert client_without_the_transform.listed_kinds == [CAR_KIND]


async def test_a_fan_out_that_was_not_widened_never_weighs_the_transform(
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
    recorded_submissions: WorkflowRecorder,
) -> None:
    """Only a widened run may stop early, so every other run lists the kind as it always did."""
    await _fan_out(widened=False)

    assert client_without_the_transform.fetched_branches == []
    assert client_without_the_transform.listed_kinds == [CAR_KIND]


async def test_a_widened_batch_skips_a_transform_deleted_after_the_widening(
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A widened fan-out passes `widened` to its chunks, so a later deletion lands here."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await _batch(coalesced=True, widened=True)

    assert client_without_the_transform.fetched_branches == [BRANCH]
    assert _warnings(caplog) == [
        f"Skipping the widened recompute of '{ATTRIBUTE_NAME}' on branch '{BRANCH}': "
        f"transform '{TRANSFORM_NAME}' is not in the database, so nothing can compute the attribute yet"
    ]


@pytest.mark.parametrize(
    "case",
    [
        _RaisingCase(name="a coalesced batch of resolved ids", coalesced=True, widened=False),
        _RaisingCase(name="a live batch", coalesced=False, widened=False),
    ],
    ids=lambda case: case.name,
)
async def test_a_batch_that_was_not_widened_raises_for_an_absent_transform(
    case: _RaisingCase,
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
) -> None:
    """Resolved ids came from a resolution that found the transform, so its absence is a fault."""
    with pytest.raises(
        ValueError,
        match=rf"^Unable to fetch transform '{TRANSFORM_NAME}' for computed attribute '{ATTRIBUTE_NAME}'$",
    ):
        await _batch(coalesced=case.coalesced, widened=case.widened)


@pytest.mark.parametrize("widened", [True, False], ids=["widened", "resolved"])
async def test_a_batch_raises_for_a_transform_it_cannot_run(
    widened: bool,
    schema_branch_with_python_attributes: None,
    client_with_an_unusable_transform: _RecordingClient,
) -> None:
    """A broken record must never be read as an absent one, on any path."""
    with pytest.raises(ValueError, match=UNUSABLE_TRANSFORM_ERROR):
        await _batch(coalesced=True, widened=widened)

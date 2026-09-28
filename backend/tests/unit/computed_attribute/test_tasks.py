from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Generator

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

LOGGER_NAME = "infrahub.computed_attribute.tasks"
BRANCH = "main"
CAR_KIND = "TestingCar"
ATTRIBUTE_NAME = "description"
TRANSFORM_NAME = "transform_a"
STALE_TRANSFORM_NAME = "transform_the_branch_renamed"

UNCONFIGURED_ATTRIBUTE = "no_transform_named"

# The shape the API answers with when no transform matches the filter.
NO_TRANSFORM_FOUND: dict[str, Any] = {"CoreTransformPython": {"edges": []}}


def _transform_payload(repository: dict[str, Any] | None) -> dict[str, Any]:
    """One transform edge, with or without the repository peer a run needs."""
    return {
        "CoreTransformPython": {
            "edges": [
                {
                    "node": {
                        "id": "txfm-001",
                        "file_path": {"value": "transforms/t.py"},
                        "class_name": {"value": "T"},
                        "timeout": {"value": 60},
                        "convert_query_response": {"value": False},
                        "repository": {"node": repository},
                        "query": {"node": {"id": "query-001", "name": {"value": "q"}}},
                    }
                }
            ]
        }
    }


USABLE_TRANSFORM = _transform_payload(
    {
        "id": "repo-001",
        "__typename": "CoreReadOnlyRepository",
        "name": {"value": "repo01"},
        "commit": {"value": "commit01"},
    }
)

# In the database and not runnable: the repository peer is gone.
TRANSFORM_WITHOUT_A_REPOSITORY = _transform_payload(None)

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

    def __init__(
        self, transform_response: dict[str, Any], by_transform: dict[str, dict[str, Any]] | None = None
    ) -> None:
        self._transform_response = transform_response
        self._by_transform = by_transform or {}
        self.request_context: Any = None
        self.fetched_branches: list[str] = []
        self.listed_kinds: list[str] = []

    async def execute_graphql(self, query: str, variables: dict[str, Any], branch_name: str) -> dict[str, Any]:
        self.fetched_branches.append(branch_name)
        return self._by_transform.get(variables.get("transform_name", ""), self._transform_response)

    async def all(self, kind: str, branch: str) -> list[object]:
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
def restored_registry_schema() -> Generator[None, None, None]:
    """Let a test swap the registry schema freely and put the original back."""
    original = registry._schema
    yield
    registry._schema = original


def _install_schema_branch(*attributes: AttributeSchema) -> None:
    """Point the registry at a branch whose car carries these Python attributes."""
    manager = SchemaManager()
    branch = SchemaBranch(cache={}, name=BRANCH)
    car = NodeSchema(name="Car", namespace="Testing")
    for attribute in attributes:
        branch.computed_attributes.add_python_attribute(node=car, attribute=attribute)
    manager.set_schema_branch(name=BRANCH, schema=branch)
    registry.schema = manager


@pytest.fixture
def schema_branch_with_python_attributes(restored_registry_schema: None) -> None:
    """One attribute with a transform and one without.

    The schema validator only rejects a mandatory Python attribute, so an unset transform reaches
    the widened set the same way a named one does.
    """
    _install_schema_branch(
        _python_attribute(ATTRIBUTE_NAME, TRANSFORM_NAME),
        _python_attribute(UNCONFIGURED_ATTRIBUTE, None),
    )


@pytest.fixture
def schema_branch_without_the_attribute(restored_registry_schema: None) -> None:
    """A registry that does not carry the branch, as a worker behind on the schema has."""
    registry.schema = SchemaManager()


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


class _NullDatabase:
    """Stands in for the session the converge wait is handed; no test here reads it."""

    @asynccontextmanager
    async def start_session(self) -> AsyncIterator[None]:
        yield None


@pytest.fixture(autouse=True)
def _flow_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the runtime calls the flows make outside their own logic.

    The converge wait is a no-op by default, so a skip decided on the registry the test installed
    is re-decided on that same registry. A test that cares about convergence replaces it.
    """

    async def _noop(**_kwargs: object) -> None:
        return None

    async def _database() -> _NullDatabase:
        return _NullDatabase()

    monkeypatch.setattr(tasks, "get_run_logger", lambda: logging.getLogger(LOGGER_NAME))
    monkeypatch.setattr(tasks, "add_tags", _noop)
    monkeypatch.setattr(tasks, "get_database", _database)
    monkeypatch.setattr(tasks, "get_component", _noop)
    monkeypatch.setattr(tasks, "wait_for_schema_to_converge", _noop)


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


async def _batch(*, coalesced: bool, widened: bool, attribute_name: str = ATTRIBUTE_NAME) -> None:
    await process_transform.fn(
        branch_name=BRANCH,
        node_kind=CAR_KIND,
        computed_attribute_name=attribute_name,
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


async def test_a_widened_batch_skips_an_attribute_that_names_no_transform(
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The fan-out waits this state out, and a batch it submitted has to answer the same way."""
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await _batch(coalesced=True, widened=True, attribute_name=UNCONFIGURED_ATTRIBUTE)

    assert client_without_the_transform.fetched_branches == []
    assert _warnings(caplog) == [
        f"Skipping the widened recompute of '{UNCONFIGURED_ATTRIBUTE}' on branch '{BRANCH}': "
        f"no transform is configured for it, so nothing can compute the attribute yet"
    ]


async def test_a_batch_that_was_not_widened_raises_when_no_transform_is_configured(
    schema_branch_with_python_attributes: None,
    client_without_the_transform: _RecordingClient,
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"^No transform configured for computed attribute '{UNCONFIGURED_ATTRIBUTE}'$",
    ):
        await _batch(coalesced=True, widened=False, attribute_name=UNCONFIGURED_ATTRIBUTE)


async def test_a_widened_fan_out_confirms_a_skip_against_a_converged_schema(
    restored_registry_schema: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One worker decides for the whole kind, so a stale schema must not be what skips it."""
    client = _RecordingClient(NO_TRANSFORM_FOUND, by_transform={TRANSFORM_NAME: USABLE_TRANSFORM})
    monkeypatch.setattr(tasks, "get_client", lambda: client)
    _install_schema_branch(_python_attribute(ATTRIBUTE_NAME, STALE_TRANSFORM_NAME))

    async def _converge(**_kwargs: object) -> None:
        _install_schema_branch(_python_attribute(ATTRIBUTE_NAME, TRANSFORM_NAME))

    monkeypatch.setattr(tasks, "wait_for_schema_to_converge", _converge)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await _fan_out(widened=True)

    assert _warnings(caplog) == []
    assert client.listed_kinds == [CAR_KIND]


async def test_a_widened_batch_with_a_runnable_transform_still_runs(
    schema_branch_with_python_attributes: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`widened` licenses two skips and nothing else, so a runnable transform reaches the work."""

    class _ReachedTheWorkError(Exception):
        pass

    async def _reached(**_kwargs: object) -> None:
        raise _ReachedTheWorkError

    client = _RecordingClient(USABLE_TRANSFORM)
    monkeypatch.setattr(tasks, "get_client", lambda: client)
    monkeypatch.setattr(tasks, "build_bulk_recompute_dispatcher", _reached)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME), pytest.raises(_ReachedTheWorkError):
        await _batch(coalesced=True, widened=True)

    assert _warnings(caplog) == []


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

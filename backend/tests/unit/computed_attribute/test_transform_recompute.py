from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator

import pytest

from infrahub.computed_attribute.transform_recompute import TransformRecomputeSubmitter
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.workflow import WorkflowRecorder

if TYPE_CHECKING:
    from infrahub_sdk.protocols import CoreTransformPython

BRANCH = "main"
TRANSFORM_NAME = "transform_a"
TRANSFORM_ID = "17e3f1a2-0000-0000-0000-000000000001"


@dataclass
class _StubAttributeValue:
    value: str


@dataclass
class _StubTransform:
    """A hand-written stand-in for the SDK node the fetcher returns (only ``id`` and ``name`` are read)."""

    id: str
    name: _StubAttributeValue


class _FetcherReturning:
    """A fetcher that returns a fixed transform (or nothing) for whatever id it is asked for."""

    def __init__(self, transform: _StubTransform | None) -> None:
        self._transform = transform
        self.requested_ids: list[str] = []

    async def get(
        self,
        *,
        kind: type[CoreTransformPython],
        id: str,
        branch: str,
        raise_when_missing: bool,
    ) -> CoreTransformPython | None:
        self.requested_ids.append(id)
        return self._transform  # type: ignore[return-value]  # ty: ignore[invalid-return-type]


def _computed_attribute(name: str, transform: str) -> AttributeSchema:
    return AttributeSchema(
        name=name,
        kind="Text",
        optional=True,
        computed_attribute=ComputedAttribute(kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform=transform),
    )


@pytest.fixture
def schema_branch_with_transform() -> Generator[None, None, None]:
    """Register a schema branch whose Car.description is fed by ``transform_a``.

    The registry schema is swapped for a fresh manager so the test never leaks state.
    """
    original = registry._schema
    manager = SchemaManager()
    branch = SchemaBranch(cache={}, name=BRANCH)
    car = NodeSchema(name="Car", namespace="Testing")
    branch.computed_attributes.add_python_attribute(
        node=car, attribute=_computed_attribute(name="description", transform=TRANSFORM_NAME)
    )
    manager.set_schema_branch(name=BRANCH, schema=branch)
    registry.schema = manager
    yield
    registry._schema = original


def _context() -> EventContext:
    return EventContext(branch=EventBranchContext(name=BRANCH), account_id="")


async def test_submit_fans_out_recompute_for_each_fed_attribute(
    schema_branch_with_transform: None,
) -> None:
    recorder = WorkflowRecorder()
    fetcher = _FetcherReturning(_StubTransform(id=TRANSFORM_ID, name=_StubAttributeValue(value=TRANSFORM_NAME)))
    submitter = TransformRecomputeSubmitter(client=fetcher, workflow=recorder)

    submitted = await submitter.submit(branch_name=BRANCH, transform_id=TRANSFORM_ID, context=_context())

    assert submitted == 1
    calls = recorder.get_submit_calls_for(TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES)
    assert len(calls) == 1
    assert calls[0]["parameters"]["computed_attribute_name"] == "description"
    assert calls[0]["parameters"]["computed_attribute_kind"] == "TestingCar"
    assert calls[0]["parameters"]["branch_name"] == BRANCH
    assert WorkflowTag.BRANCH.render(identifier=BRANCH) in calls[0]["tags"]


async def test_submit_skips_a_missing_transform(schema_branch_with_transform: None) -> None:
    recorder = WorkflowRecorder()
    fetcher = _FetcherReturning(None)
    submitter = TransformRecomputeSubmitter(client=fetcher, workflow=recorder)

    submitted = await submitter.submit(branch_name=BRANCH, transform_id=TRANSFORM_ID, context=_context())

    assert submitted == 0
    assert recorder.submit_calls == []
    assert fetcher.requested_ids == [TRANSFORM_ID]

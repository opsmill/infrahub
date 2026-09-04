"""A self computed attribute whose two inputs change on each side of a merge."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MergeConflictsUnresolvedError
from infrahub.workers.dependencies import (
    build_cache,
    build_component,
    build_database,
    build_event_service,
    build_workflow,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.component import build_worker_component
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SELF_SUMMARY_KIND = "TestingSelfSummary"


def _self_summary_schema() -> SchemaRoot:
    """One kind whose computed summary reads two of its own attributes."""
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="SelfSummary",
                namespace="Testing",
                default_filter="name__value",
                uniqueness_constraints=[["name__value"]],
                attributes=[
                    AttributeSchema(name="name", kind="Text", optional=False, unique=True),
                    AttributeSchema(name="description", kind="Text", optional=True),
                    AttributeSchema(
                        name="summary",
                        kind="Text",
                        optional=True,
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ name__value }} :: {{ description__value }}",
                        ),
                    ),
                ],
            ),
        ]
    )


async def test_merge_conflicts_when_a_self_attribute_input_changes_on_each_side(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    dependency_provider: Provider,
) -> None:
    lock.initialize_lock(local_only=True)
    await load_schema(db=db, schema=_self_summary_schema(), update_db=True)

    node = await Node.init(db=db, schema=SELF_SUMMARY_KIND, branch=default_branch)
    await node.new(db=db, name="n0", description="d0")
    await node.save(db=db)
    assert node.summary.value == "n0 :: d0"

    branch = await create_branch(branch_name="two-sided-self", db=db)

    # The branch edits the description; its inline recompute sees the new description, old name.
    on_branch = await NodeManager.get_one(db=db, id=node.id, branch=branch)
    on_branch.description.value = "d1"
    await on_branch.save(db=db)
    assert on_branch.summary.value == "n0 :: d1"

    # The destination edits the name after the fork; the branch diff never carries this.
    on_main = await NodeManager.get_one(db=db, id=node.id, branch=default_branch)
    on_main.name.value = "n1"
    await on_main.save(db=db)
    assert on_main.summary.value == "n1 :: d0"

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

    event_recorder = MemoryInfrahubEvent()
    workflow_recorder = WorkflowRecorder()
    cache = MemoryCache()
    component = await build_worker_component(db=db, cache=cache)
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    # Each side recomputed the summary to a different value, so the merge's conflict gate blocks it
    # rather than committing a value that reflects only one of the two edits.
    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_workflow, lambda: workflow_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
        dependency_provider.scope(build_component, lambda: component),
        pytest.raises(
            MergeConflictsUnresolvedError,
            match=r"^Unable to merge the branch 'two-sided-self', conflict resolution missing:.*summary/value",
        ),
    ):
        await merge_branch(branch=branch.name, context=context)

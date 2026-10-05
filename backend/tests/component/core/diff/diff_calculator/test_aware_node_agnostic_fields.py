"""Diff coverage for the AWARE node + AGNOSTIC fields scenario.

Retirement of branch-agnostic fields writes `to` stamps on global-branch edges, and a `to` stamp
is the very signal by which deletes normally register in a diff. The diff traversal includes
global-branch edges, so nothing structural prevents those stamps from surfacing as changes on a
branch that never saw the object. The test pins the guarantee at the layer a user sees: the
enriched diff reported for the branch, not the raw edges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.agnostic_edges import attribute_global_edges, open_edges, relationship_global_edges
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def agnostic_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The diff machinery resolves core kinds while it synchronizes, so the core schema rides along."""
    registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


async def test_a_branch_that_forked_before_the_retirement_reports_no_change_for_the_node(
    db: InfrahubDatabase,
    default_branch: Branch,
    agnostic_schema: None,
) -> None:
    """The close lands on global edges inside the branch's diff window, and must not surface there.

    The branch forked before the object existed, so it retains nothing and the default-branch
    delete really does close the global edges -- the shape this guarantee is about. Those closes are
    stamps on global-branch edges, which the branch's diff shouldn't read, so a diff that treated
    a `to` stamp as a removal would report attribute and relationship changes for an object the
    branch has never seen.
    """
    branch = await create_branch(db=db, branch_name="forked-before-the-node-existed")

    gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
    await gadget.new(db=db, name="peer-invisible-to-the-fork")
    await gadget.save(db=db)
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="retired-after-the-fork", serial=2300, gadget=gadget)
    await widget.save(db=db)
    assert await NodeManager.get_one(db=db, id=widget.id, branch=branch) is None, (
        "the branch forked before the creation, so it cannot retain the object"
    )

    deleted_at = Timestamp()
    to_delete = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
    await to_delete.delete(db=db, at=deleted_at)

    attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
    assert open_edges(attribute_after) == [], "the retirement must actually close for the claim to mean anything"
    relationship_after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert open_edges(relationship_after) == []

    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
    branch_diff = await diff_repository.get_one(diff_branch_name=metadata.diff_branch_name, diff_id=metadata.uuid)

    reported = {node.uuid: node for node in branch_diff.nodes if node.uuid in {widget.id, gadget.id}}
    assert not reported, (
        "the retirement registered on a branch that forked before it: "
        f"{[(node.uuid, node.action) for node in reported.values()]}"
    )

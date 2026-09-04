"""The merge enforcement point: retention is re-evaluated for the deletions the merge carries.

The merge is never the release trigger. It re-runs the same predicate the delete point runs,
over the nodes its own diff records as removed, and acts only on the result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

from tests.component.core.agnostic_retirement.support import delete_node
from tests.helpers.agnostic_edges import (
    TEST_ACTOR_ID,
    assert_attribute_retired_at,
    assert_relationship_retired_at,
    attribute_global_edges,
    create_widget,
    edge_summary,
    open_edge_types,
    relationship_global_edges,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
)


async def _update_branch_diff(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> EnrichedDiffRoot:
    """Recompute the branch's tracked diff and return the enriched branch-side diff root."""
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    metadata = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)
    return await diff_repository.get_one(diff_branch_name=metadata.diff_branch_name, diff_id=metadata.uuid)


async def _merge_branch(db: InfrahubDatabase, default_branch: Branch, branch: Branch, at: Timestamp) -> None:
    """Merge the branch's graph into the default branch, the way the merge flow drives it."""
    await _update_branch_diff(db=db, default_branch=default_branch, branch=branch)
    component_registry = get_component_registry()
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_merger.merge_graph(at=at, user_id=TEST_ACTOR_ID)


class TestAgnosticRetirementOnMerge:
    @pytest.fixture(scope="class")
    async def default_branch(self, default_branch_scope_class: Branch) -> Branch:
        return default_branch_scope_class

    @pytest.fixture(scope="class")
    async def agnostic_schema(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        """The diff machinery resolves core kinds while it synchronizes, so the core schema rides along."""
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)

    async def test_merging_the_deletion_of_the_last_holder_closes_the_field(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Merging the final delete of an object deletes its agnostic fields.

        Deleting on the branch closes nothing, because the default branch still reads the object.
        Merging the branch carries the deletion over, after which no branch reads it, so the merge's
        re-evaluation closes the attribute's and the relationship's global edges at the merge time.
        """
        gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await gadget.new(db=db, name="peer-of-the-merged-deletion")
        await gadget.save(db=db)
        widget = await create_widget(
            db=db, branch=default_branch, name="deleted-then-merged", serial=2100, gadget=gadget
        )
        branch = await create_branch(db=db, branch_name="merges-its-deletion")

        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(attribute_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}
        relationship_before = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )

        await delete_node(db=db, node_id=widget.id, branch=branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        ), "the default branch still reads the object, so the branch's delete released nothing"

        merged_at = Timestamp()
        await _merge_branch(db=db, default_branch=default_branch, branch=branch, at=merged_at)

        assert await NodeManager.get_one(db=db, id=widget.id, branch=default_branch) is None, (
            "the merge carried the deletion to the default branch"
        )
        attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=attribute_after, before=attribute_before, at=merged_at, by=TEST_ACTOR_ID)
        relationship_after = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )
        assert_relationship_retired_at(
            after=relationship_after, before=relationship_before, at=merged_at, by=TEST_ACTOR_ID
        )

    async def test_merging_the_deletion_releases_nothing_while_another_branch_retains_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """The merge re-evaluates and defers: a branch that still reads the object keeps it reserved."""
        widget = await create_widget(db=db, branch=default_branch, name="retained-through-a-merge", serial=2200)
        retainer = await create_branch(db=db, branch_name="retains-through-the-merge")
        branch = await create_branch(db=db, branch_name="deletes-and-merges")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=widget.id, branch=branch, at=Timestamp())
        await _merge_branch(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

        assert await NodeManager.get_one(db=db, id=widget.id, branch=default_branch) is None, (
            "the merge carried the deletion to the default branch"
        )
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the retaining branch still reads the object, so the merge released nothing"
        on_retainer = await NodeManager.get_one(db=db, id=widget.id, branch=retainer)
        assert on_retainer is not None
        assert on_retainer.get_attribute(name="serial").value == 2200

    async def test_merging_two_deletions_together_evaluates_retention_per_node(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """One merge carries two deletions, and each candidate is judged on its own retainers.

        Both nodes travel to the re-evaluation together, so a verdict computed over the set as a
        whole would either leak the retained node or wrongly hold the unretained one. The branch
        that forked between the two creations reads only the older node, so that node stays open
        while the younger one closes at the merge time.
        """
        retained = await create_widget(db=db, branch=default_branch, name="retained-half-of-the-pair", serial=2610)
        retainer = await create_branch(db=db, branch_name="retains-half-of-the-pair")
        unretained = await create_widget(db=db, branch=default_branch, name="unretained-half-of-the-pair", serial=2620)
        branch = await create_branch(db=db, branch_name="deletes-the-pair-and-merges")

        retained_before = await attribute_global_edges(db=db, node_id=retained.id, attribute_name="serial")
        unretained_before = await attribute_global_edges(db=db, node_id=unretained.id, attribute_name="serial")
        assert open_edge_types(retained_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}
        assert open_edge_types(unretained_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=retained.id, branch=branch, at=Timestamp())
        await delete_node(db=db, node_id=unretained.id, branch=branch, at=Timestamp())

        merged_at = Timestamp()
        await _merge_branch(db=db, default_branch=default_branch, branch=branch, at=merged_at)

        assert await NodeManager.get_one(db=db, id=retained.id, branch=default_branch) is None, (
            "the merge carried both deletions to the default branch"
        )
        assert await NodeManager.get_one(db=db, id=unretained.id, branch=default_branch) is None

        unretained_after = await attribute_global_edges(db=db, node_id=unretained.id, attribute_name="serial")
        assert_attribute_retired_at(after=unretained_after, before=unretained_before, at=merged_at, by=TEST_ACTOR_ID)
        assert edge_summary(await attribute_global_edges(db=db, node_id=retained.id, attribute_name="serial")) == (
            edge_summary(retained_before)
        ), "its neighbor's release must not drag the retained node's fields shut with it"
        on_retainer = await NodeManager.get_one(db=db, id=retained.id, branch=retainer)
        assert on_retainer is not None
        assert on_retainer.get_attribute(name="serial").value == 2610

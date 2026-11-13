"""The branch-deletion enforcement point: retention is re-evaluated for what the branch could reach.

Branch-agnostic fields that become unreachable during a branch's delete must be closed. If the
field is still accessible from any other branch, it must remain accessible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

from tests.component.core.agnostic_retirement.support import (
    FailingBranchRetirementDatabase,
    RetirementFailureError,
    delete_node,
    merge_branch,
)
from tests.helpers.agnostic_edges import (
    TEST_ACTOR_ID,
    assert_attribute_retired_at,
    assert_relationship_retired_at,
    attribute_global_edges,
    create_widget,
    edge_summary,
    open_edge_types,
    open_edges,
    relationship_global_edges,
    to_times,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
)


class TestAgnosticRetirementOnBranchDelete:
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
        """The merge a test drives resolves core kinds while it synchronizes, so the core schema rides along."""
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)

    async def _branch_vertex_count(self, db: InfrahubDatabase, branch_name: str) -> int:
        results = await db.execute_query(
            query="MATCH (b:Branch {name: $branch_name}) RETURN count(b) AS branch_count",
            params={"branch_name": branch_name},
        )
        return results[0]["branch_count"]

    async def test_deleting_the_last_retaining_branch_closes_the_field(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """A deletion deferred by an open branch is released when that branch is deleted.

        The branch forked while the object was live, so the default-branch delete closed nothing --
        the object has no edge on the branch at all; it is retained purely through the fork window.
        Deleting the branch empties the retaining set, and the deleter's re-evaluation closes the
        attribute's and the relationship's global edges in one pass, all at the deletion's own stamp.
        """
        gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await gadget.new(db=db, name="peer-of-the-branch-deleted-retainee")
        await gadget.save(db=db)
        widget = await create_widget(
            db=db, branch=default_branch, name="released-by-a-branch-delete", serial=3100, gadget=gadget
        )
        branch = await create_branch(db=db, branch_name="last-retainer-gets-deleted")

        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(attribute_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}
        relationship_before = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        ), "the branch still reads the object through its fork window, so the delete released nothing"

        lower_bound = Timestamp()
        result = await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch, user_id=TEST_ACTOR_ID)
        upper_bound = Timestamp()
        assert result.branch_deleted

        attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        relationship_after = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )
        stamps = to_times(attribute_after) | to_times(relationship_after)
        assert len(stamps) == 1, "the whole run closes at one stamp"
        (stamp,) = stamps
        assert stamp is not None
        assert lower_bound.to_string() <= stamp <= upper_bound.to_string(), (
            "the close carries the branch deletion's own time"
        )
        retired_at = Timestamp(stamp)
        assert_attribute_retired_at(after=attribute_after, before=attribute_before, at=retired_at, by=TEST_ACTOR_ID)
        assert_relationship_retired_at(
            after=relationship_after, before=relationship_before, at=retired_at, by=TEST_ACTOR_ID
        )

    async def test_deleting_a_branch_releases_nothing_while_another_branch_retains_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """The branch delete re-evaluates and defers: a branch that still reads the object keeps it reserved.

        Deleting the second retainer afterwards is what empties the set, proving the deferral is
        re-evaluated at the next branch deletion rather than lost.
        """
        widget = await create_widget(db=db, branch=default_branch, name="retained-past-a-branch-delete", serial=3200)
        retainer = await create_branch(db=db, branch_name="outlives-its-sibling")
        doomed = await create_branch(db=db, branch_name="first-of-two-retainers-to-go")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        await BranchDataDeleter(db=db, batch_size=5).delete(branch=doomed, user_id=TEST_ACTOR_ID)

        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the surviving branch still reads the object, so the branch delete released nothing"
        on_retainer = await NodeManager.get_one(db=db, id=widget.id, branch=retainer)
        assert on_retainer is not None
        assert on_retainer.get_attribute(name="serial").value == 3200

        await BranchDataDeleter(db=db, batch_size=5).delete(branch=retainer, user_id=TEST_ACTOR_ID)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edges(after) == [], "the last retainer's deletion released it"
        assert {edge.status for edge in after} == {"active"}

    async def test_a_release_larger_than_the_batch_closes_every_candidate_at_one_stamp(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Retention is evaluated per batch of Nodes, and the batching is invisible in the result.

        A batch smaller than the candidate set must still release every candidate, attribute and
        relationship alike, and every closure carries the one stamp of the deletion rather than a
        stamp per batch.
        """
        widgets = []
        for index in range(5):
            gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
            await gadget.new(db=db, name=f"peer-of-batched-release-{index}")
            await gadget.save(db=db)
            widgets.append(
                await create_widget(
                    db=db, branch=default_branch, name=f"batched-release-{index}", serial=3400 + index, gadget=gadget
                )
            )
        branch = await create_branch(db=db, branch_name="released-in-batches")

        before = {
            widget.id: (
                await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial"),
                await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER),
            )
            for widget in widgets
        }
        for widget in widgets:
            await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())

        lower_bound = Timestamp()
        result = await BranchDataDeleter(db=db, batch_size=2).delete(branch=branch, user_id=TEST_ACTOR_ID)
        upper_bound = Timestamp()
        assert result.branch_deleted

        stamps: set[str | None] = set()
        after = {}
        for widget in widgets:
            attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
            relationship_after = await relationship_global_edges(
                db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
            )
            assert open_edges(attribute_after) == [], f"widget {widget.id} kept an open attribute edge"
            assert open_edges(relationship_after) == [], f"widget {widget.id} kept an open relationship edge"
            after[widget.id] = (attribute_after, relationship_after)
            stamps |= to_times(attribute_after) | to_times(relationship_after)

        assert len(stamps) == 1, "every batch closes at the deletion's one stamp"
        (stamp,) = stamps
        assert stamp is not None
        assert lower_bound.to_string() <= stamp <= upper_bound.to_string()
        retired_at = Timestamp(stamp)
        for widget in widgets:
            attribute_before, relationship_before = before[widget.id]
            attribute_after, relationship_after = after[widget.id]
            assert_attribute_retired_at(after=attribute_after, before=attribute_before, at=retired_at, by=TEST_ACTOR_ID)
            assert_relationship_retired_at(
                after=relationship_after, before=relationship_before, at=retired_at, by=TEST_ACTOR_ID
            )

    async def test_deleting_a_merged_branch_releases_what_the_default_branch_deleted_since(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """The other candidate bound: an object that exists on the deleted branch itself.

        Created on the branch and merged, the object is read on the branch through its own existence
        edge rather than through the fork window. The default-branch delete closes nothing while the
        merged branch still reads it; deleting that branch is what empties the retaining set.
        """
        branch = await create_branch(db=db, branch_name="merged-then-deleted")
        widget = await create_widget(db=db, branch=branch, name="born-on-the-merged-branch", serial=3500)
        await merge_branch(db=db, default_branch=default_branch, branch=branch, at=Timestamp())

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the merged branch still reads the object, so the default-branch delete released nothing"

        lower_bound = Timestamp()
        result = await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch, user_id=TEST_ACTOR_ID)
        upper_bound = Timestamp()
        assert result.branch_deleted

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edges(after) == [], "the merged branch was the last retainer"
        (stamp,) = to_times(after)
        assert stamp is not None
        assert lower_bound.to_string() <= stamp <= upper_bound.to_string()
        assert_attribute_retired_at(after=after, before=before, at=Timestamp(stamp), by=TEST_ACTOR_ID)

    async def test_a_retirement_failure_fails_the_branch_delete(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """The failure has to reach the caller, and the interrupted delete stays resumable.

        Swallowing it would remove the branch's edges next, destroying the reachability information
        the re-evaluation needs -- the leak would be permanent, with only the repair migration left
        to find it. The branch vertex survives the failed attempt, so running the delete again
        finishes the release.
        """
        widget = await create_widget(db=db, branch=default_branch, name="branch-delete-fails-first", serial=3300)
        branch = await create_branch(db=db, branch_name="deletion-interrupted-by-the-failure")

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        failing_db = FailingBranchRetirementDatabase.from_db(db=db)
        with pytest.raises(RetirementFailureError, match=r"^the retirement run could not complete$"):
            await BranchDataDeleter(db=failing_db, batch_size=5).delete(branch=branch)

        assert await self._branch_vertex_count(db=db, branch_name=branch.name) == 1, (
            "the failed delete must stop before removing the branch, or the leak could never be re-evaluated"
        )
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the failed run closed nothing"

        result = await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch, user_id=TEST_ACTOR_ID)
        assert result.branch_deleted
        assert await self._branch_vertex_count(db=db, branch_name=branch.name) == 0
        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edges(after) == [], "resuming the delete completes the release"

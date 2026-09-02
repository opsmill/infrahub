"""The node-delete enforcement point for branch-agnostic fields.

Deleting a branch-aware object closes its branch-agnostic fields' global edges only when no branch
can still read the object; any surviving reader defers the release to a later enforcement point.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

from tests.component.core.agnostic_retirement.support import (
    FailingRetirementDatabase,
    RetirementFailureError,
    delete_node,
)
from tests.helpers.agnostic_edges import (
    TEST_ACTOR_ID,
    assert_attribute_retired_at,
    assert_relationship_retired_at,
    attribute_global_edges,
    attribute_owning_edges,
    create_widget,
    edge_summary,
    existence_edges,
    open_edge_types,
    open_edges,
    pool_reservation_edges,
    relationship_global_edges,
    remove_attribute_on_branch,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)

SERIAL_POOL_START = 9001
SERIAL_POOL_END = 9002


class TestAgnosticRetirementOnDelete:
    @pytest.fixture(scope="class")
    async def default_branch(self, default_branch_scope_class: Branch) -> Branch:
        return default_branch_scope_class

    @pytest.fixture(scope="class")
    async def agnostic_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)

    @pytest.fixture(scope="class")
    async def serial_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> CoreNumberPool:
        """A pool of two numbers backing the widget's branch-agnostic serial.

        Two rather than one so that an allocation which fails to reuse the freed value still succeeds,
        and reports the number it handed out instead of an exhausted pool.
        """
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
        await pool.new(
            db=db,
            name="agnostic-serial-pool",
            node=WIDGET_KIND,
            node_attribute="serial",
            start_range=SERIAL_POOL_START,
            end_range=SERIAL_POOL_END,
        )
        await pool.save(db=db)
        return pool

    async def test_a_field_created_and_deleted_on_the_same_user_branch_is_closed_by_the_delete(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """An object that only ever existed on one branch cannot also exist elsewhere through a merge.

        A branch that has been merged is permanently read-only, so a delete running on a branch proves the
        branch was never merged. Nothing else can be holding the field, so the close is unconditional.
        """
        branch = await create_branch(db=db, branch_name="creates-and-deletes")
        widget = await create_widget(db=db, branch=branch, name="branch-only", serial=100)

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)

    async def test_a_field_stays_open_while_the_default_branch_still_holds_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Deleting on a branch says nothing about the object's fate on the branch it forked from."""
        widget = await create_widget(db=db, branch=default_branch, name="deleted-on-a-branch-only", serial=200)
        branch = await create_branch(db=db, branch_name="deletes-its-own-copy")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        await delete_node(db=db, node_id=widget.id, branch=branch, at=Timestamp())

        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        )
        still_on_default = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch)
        assert still_on_default is not None
        assert still_on_default.get_attribute(name="serial").value == 200

    async def test_a_field_is_closed_when_the_default_branch_deletes_the_last_holder(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """No branch forked between the creation and the deletion, so no branch can still read the object."""
        widget = await create_widget(db=db, branch=default_branch, name="last-holder", serial=300)

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)

    async def test_a_field_stays_open_for_a_branch_that_forked_between_creation_and_deletion(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """A branch that forked while the object was live reads it as live, and keeps reading its value."""
        widget = await create_widget(db=db, branch=default_branch, name="retained-by-a-fork", serial=400)
        branch = await create_branch(db=db, branch_name="forked-before-the-delete")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())

        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        )
        assert await NodeManager.get_one(db=db, id=widget.id, branch=default_branch) is None
        on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch)
        assert on_branch is not None
        assert on_branch.get_attribute(name="serial").value == 400

    async def test_a_field_stays_open_until_every_retaining_branch_has_deleted_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Verify that an object's agnostic fields are only deleted when NO branch can reach them"""
        widget = await create_widget(db=db, branch=default_branch, name="held-by-two", serial=800)
        first = await create_branch(db=db, branch_name="first-of-two-holders")
        second = await create_branch(db=db, branch_name="second-of-two-holders")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "two branches still read the object, so nothing is released"

        await delete_node(db=db, node_id=widget.id, branch=first, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the second branch alone is still enough to retain it"
        assert await NodeManager.get_one(db=db, id=widget.id, branch=second) is not None

        last_delete = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=second, at=last_delete)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=after, before=before, at=last_delete, by=TEST_ACTOR_ID)

    async def test_an_attribute_that_accumulated_value_edges_is_closed_edge_for_edge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """A value update leaves a second `HAS_VALUE` edge, and the delete's close is per edge, not per type.

        The superseded edge keeps the stamp the update gave it, so the closed shape holds two
        `HAS_VALUE` rows carrying two different stamps.
        """
        widget = await create_widget(db=db, branch=default_branch, name="value-updated-then-deleted", serial=900)
        to_update = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
        to_update.get_attribute(name="serial").value = 901
        await to_update.save(db=db)

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert sorted((edge.edge_type, edge.is_open) for edge in before) == [
            ("HAS_ATTRIBUTE", True),
            ("HAS_VALUE", False),
            ("HAS_VALUE", True),
            ("IS_PROTECTED", True),
        ], "precondition: the update time-closed the superseded value edge and left the new one open"

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)

    async def test_a_repointed_relationship_is_closed_edge_for_edge(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """A peer update leaves a superseded relationship vertex, and the delete's close is per edge.

        The superseded vertex's edges keep the stamp the update gave them, so the closed shape holds
        two sets of peer edges carrying two different stamps.
        """
        first_peer = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await first_peer.new(db=db, name="superseded-peer")
        await first_peer.save(db=db)
        second_peer = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await second_peer.new(db=db, name="replacement-peer")
        await second_peer.save(db=db)
        widget = await create_widget(
            db=db, branch=default_branch, name="repointed-then-deleted", serial=1200, gadget=first_peer
        )

        to_update = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
        await to_update.get_relationship(name="gadget").update(db=db, data=second_peer)
        await to_update.save(db=db)

        before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert sorted((edge.edge_type, edge.is_open) for edge in before) == [
            ("IS_PROTECTED", False),
            ("IS_PROTECTED", True),
            ("IS_RELATED", False),
            ("IS_RELATED", False),
            ("IS_RELATED", True),
            ("IS_RELATED", True),
        ], "precondition: the update time-closed the superseded vertex's edges and opened the replacement's"

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

        after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert_relationship_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)

    async def test_a_relationship_is_closed_when_its_peers_are_live_on_different_branches(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Both peers must be live under one branch's view, not one peer each on two branches.

        After deleting each peer on a separate branch, the object is NOT retired. Only when the
        relationship is broken on _every_ branch will it be retired.
        """
        gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await gadget.new(db=db, name="peer-on-its-own-branch")
        await gadget.save(db=db)
        widget = await create_widget(db=db, branch=default_branch, name="split-peers", serial=1100, gadget=gadget)

        keeps_the_gadget = await create_branch(db=db, branch_name="keeps-the-gadget")
        keeps_the_widget = await create_branch(db=db, branch_name="keeps-the-widget")

        before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

        # each branch loses one half of the relationship, so neither branch holds both peers
        await delete_node(db=db, node_id=widget.id, branch=keeps_the_gadget, at=Timestamp())
        await delete_node(db=db, node_id=gadget.id, branch=keeps_the_widget, at=Timestamp())

        assert edge_summary(
            await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        ) == edge_summary(before), "the default branch still holds both peers"

        last_delete = Timestamp()
        await delete_node(db=db, node_id=gadget.id, branch=default_branch, at=last_delete)

        after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert_relationship_retired_at(after=after, before=before, at=last_delete, by=TEST_ACTOR_ID)

    async def test_a_field_removed_on_the_only_retaining_branch_is_closed_with_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Test an attribute removed from the schema on a branch is retired when its object is deleted."""
        widget = await create_widget(db=db, branch=default_branch, name="field-removed-on-the-fork", serial=500)
        branch = await create_branch(db=db, branch_name="removed-the-attribute")
        await remove_attribute_on_branch(
            db=db, node_id=widget.id, attribute_name="serial", branch=branch, at=Timestamp()
        )

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)

        owning_edges = await attribute_owning_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert sorted((edge.branch, edge.status, edge.to_time or "") for edge in owning_edges) == [
            (GLOBAL_BRANCH_NAME, "active", deleted_at.to_string()),
            (default_branch.name, "deleted", ""),
            (branch.name, "deleted", ""),
        ], "only the global edge is closed; the branch-scoped tombstones are left exactly as they were"

        still_on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch)
        assert still_on_branch is not None, "the branch retains the object, which is why only the field was released"
        assert still_on_branch.get_attribute(name="serial").value is None, (
            "the branch that dropped the field reads no value for it, which is what made it unretained"
        )

    async def test_a_relationship_is_closed_when_one_of_its_peers_is_deleted(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """A relationship missing a peer is not a relationship, so both of its peer edges are closed."""
        gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await gadget.new(db=db, name="doomed-peer")
        await gadget.save(db=db)
        widget = await create_widget(db=db, branch=default_branch, name="surviving-peer", serial=600, gadget=gadget)

        before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=gadget.id, branch=default_branch, at=deleted_at)

        after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert_relationship_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)

    async def test_a_retirement_failure_propagates_and_leaves_the_graph_untouched(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """The failure has to reach the caller, because the deletion is what rolls back with it.

        Reporting the failure as a zero commits a deleted object still holding a live branch-agnostic
        value, which is the shape retirement exists to prevent and which no later action repairs.
        """
        widget = await create_widget(db=db, branch=default_branch, name="delete-rolls-back", serial=700)

        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        existence_before = await existence_edges(db=db, node_id=widget.id)

        failing_db = FailingRetirementDatabase.from_db(db=db)
        with pytest.raises(RetirementFailureError, match=r"^the retirement run could not complete$"):
            async with failing_db.start_transaction() as dbt:
                to_delete = await NodeManager.get_one(db=dbt, id=widget.id, branch=default_branch, raise_on_error=True)
                await to_delete.delete(db=dbt, at=Timestamp())

        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        )
        assert sorted((edge.branch, edge.status, edge.to_time or "") for edge in existence_before) == sorted(
            (edge.branch, edge.status, edge.to_time or "") for edge in await existence_edges(db=db, node_id=widget.id)
        ), "the existence tombstone rolled back with the retirement that failed after it"
        still_there = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch)
        assert still_there is not None
        assert still_there.get_attribute(name="serial").value == 700

    async def test_a_value_freed_by_retirement_is_allocatable_again_from_its_pool(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        serial_pool: CoreNumberPool,
    ) -> None:
        """Deleting the object holding a pooled value returns that value to the pool."""
        holder = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
        await holder.new(db=db, name="holds-a-pooled-serial", serial={"from_pool": {"id": serial_pool.id}})
        await holder.save(db=db)

        assert holder.get_attribute(name="serial").value == SERIAL_POOL_START
        assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]

        before = await attribute_global_edges(db=db, node_id=holder.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED", "HAS_SOURCE"}
        reserved_before = await pool_reservation_edges(db=db, pool_id=serial_pool.id, identifier=holder.id)
        assert [(edge.edge_type, edge.branch, edge.status, edge.to_time) for edge in reserved_before] == [
            ("IS_RESERVED", GLOBAL_BRANCH_NAME, "active", None)
        ]

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=holder.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=holder.id, attribute_name="serial")
        assert_attribute_retired_at(after=after, before=before, at=deleted_at, by=TEST_ACTOR_ID)
        assert await pool_reservation_edges(db=db, pool_id=serial_pool.id, identifier=holder.id) == reserved_before, (
            "the reservation is never cleaned up on delete, and does not need to be"
        )
        assert await serial_pool.get_used(db=db, branch=default_branch) == []

        reallocated = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
        await reallocated.new(db=db, name="takes-the-freed-serial", serial={"from_pool": {"id": serial_pool.id}})
        await reallocated.save(db=db)

        assert reallocated.get_attribute(name="serial").value == SERIAL_POOL_START
        assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]

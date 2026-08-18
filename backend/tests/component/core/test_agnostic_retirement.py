"""Test for deleting branch-aware objects with branch-agnostic attributes and relationships.

Branch-agnostic fields on branch-aware objects should only be deleted when the cannot be accessed
from any branch.

Every assertion reads the edges directly rather than going through the node manager: the subject is
which edges carry a `to` timestamp and which do not, and a read through the manager would hide the
very states these tests exist to pin down. Where a branch is expected to go on reading the object, the
manager is used as well, because that is the claim being made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node_agnostic_retirement import RetireNodeAgnosticFieldsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode

if TYPE_CHECKING:
    from neo4j import Record

    from infrahub.core.branch import Branch
    from infrahub.core.query import QueryType

from tests.helpers.agnostic_edges import (
    attribute_global_edges,
    attribute_owning_edges,
    edge_summary,
    existence_edges,
    expected_closed_at,
    open_edge_types,
    open_edges,
    relationship_global_edges,
    remove_attribute_on_branch,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)


class RetirementFailureError(Exception):
    """Stands in for whatever the retirement run could fail with."""


class FailingRetirementDatabase(InfrahubDatabase):
    """Database that fails the branch-agnostic retirement query and passes every other query through.

    A real database is what makes the claim testable: the deletion's own writes have to reach the
    transaction so that the rollback has something to undo.
    """

    @classmethod
    def from_db(cls, db: InfrahubDatabase) -> FailingRetirementDatabase:
        return cls(
            mode=InfrahubDatabaseMode.DRIVER,
            driver=db._driver,
            db_type=db.db_type,
            default_neo4j_runtime=db.default_neo4j_runtime,
            queries_names_to_config=db.queries_names_to_config,
        )

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        if name == RetireNodeAgnosticFieldsQuery.name:
            raise RetirementFailureError("the retirement run could not complete")
        return await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )


async def _create_widget(db: InfrahubDatabase, branch: Branch, name: str, serial: int, **kwargs: Any) -> Node:
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name=name, serial=serial, **kwargs)
    await widget.save(db=db)
    return widget


async def _delete(db: InfrahubDatabase, node_id: str, branch: Branch, at: Timestamp) -> None:
    to_delete = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    await to_delete.delete(db=db, at=at)


class TestAgnosticRetirementOnDelete:
    @pytest.fixture(scope="class")
    async def default_branch(self, default_branch_scope_class: Branch) -> Branch:
        return default_branch_scope_class

    @pytest.fixture(scope="class")
    async def agnostic_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)

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
        widget = await _create_widget(db=db, branch=branch, name="branch-only", serial=100)

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        deleted_at = Timestamp()
        await _delete(db=db, node_id=widget.id, branch=branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert edge_summary(after) == expected_closed_at(before, deleted_at)
        assert {edge.status for edge in after} == {"active"}, "retirement is a time-close, never a status tombstone"

    async def test_a_field_stays_open_while_the_default_branch_still_holds_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Deleting on a branch says nothing about the object's fate on the branch it forked from."""
        widget = await _create_widget(db=db, branch=default_branch, name="deleted-on-a-branch-only", serial=200)
        branch = await create_branch(db=db, branch_name="deletes-its-own-copy")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        await _delete(db=db, node_id=widget.id, branch=branch, at=Timestamp())

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
        widget = await _create_widget(db=db, branch=default_branch, name="last-holder", serial=300)

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        deleted_at = Timestamp()
        await _delete(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert edge_summary(after) == expected_closed_at(before, deleted_at)
        assert {edge.status for edge in after} == {"active"}, "retirement is a time-close, never a status tombstone"

    async def test_a_field_stays_open_for_a_branch_that_forked_between_creation_and_deletion(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """A branch that forked while the object was live reads it as live, and keeps reading its value."""
        widget = await _create_widget(db=db, branch=default_branch, name="retained-by-a-fork", serial=400)
        branch = await create_branch(db=db, branch_name="forked-before-the-delete")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await _delete(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())

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
        widget = await _create_widget(db=db, branch=default_branch, name="held-by-two", serial=800)
        first = await create_branch(db=db, branch_name="first-of-two-holders")
        second = await create_branch(db=db, branch_name="second-of-two-holders")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await _delete(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "two branches still read the object, so nothing is released"

        await _delete(db=db, node_id=widget.id, branch=first, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the second branch alone is still enough to retain it"
        assert await NodeManager.get_one(db=db, id=widget.id, branch=second) is not None

        last_delete = Timestamp()
        await _delete(db=db, node_id=widget.id, branch=second, at=last_delete)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edges(after) == [], "the last holder released it"
        assert {edge.to_time for edge in after} == {last_delete.to_string()}

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
        widget = await _create_widget(db=db, branch=default_branch, name="split-peers", serial=1100, gadget=gadget)

        keeps_the_gadget = await create_branch(db=db, branch_name="keeps-the-gadget")
        keeps_the_widget = await create_branch(db=db, branch_name="keeps-the-widget")

        before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

        # each branch loses one half of the relationship, so neither branch holds both peers
        await _delete(db=db, node_id=widget.id, branch=keeps_the_gadget, at=Timestamp())
        await _delete(db=db, node_id=gadget.id, branch=keeps_the_widget, at=Timestamp())

        assert edge_summary(
            await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        ) == edge_summary(before), "the default branch still holds both peers"

        last_delete = Timestamp()
        await _delete(db=db, node_id=gadget.id, branch=default_branch, at=last_delete)

        after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert open_edges(after) == [], (
            "no branch reads both peers as live, so the relationship is released even though each peer "
            "survives somewhere"
        )

    async def test_a_field_removed_on_the_only_retaining_branch_is_closed_with_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
    ) -> None:
        """Test an attribute removed from the schema on a branch is retired when its object is deleted."""
        widget = await _create_widget(db=db, branch=default_branch, name="field-removed-on-the-fork", serial=500)
        branch = await create_branch(db=db, branch_name="removed-the-attribute")
        await remove_attribute_on_branch(
            db=db, node_id=widget.id, attribute_name="serial", branch=branch, at=Timestamp()
        )

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        deleted_at = Timestamp()
        await _delete(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert edge_summary(after) == expected_closed_at(before, deleted_at)
        assert {edge.status for edge in after} == {"active"}, "retirement is a time-close, never a status tombstone"

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
        widget = await _create_widget(db=db, branch=default_branch, name="surviving-peer", serial=600, gadget=gadget)

        before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

        deleted_at = Timestamp()
        await _delete(db=db, node_id=gadget.id, branch=default_branch, at=deleted_at)

        after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
        assert open_edges(after) == []
        assert {edge.status for edge in after} == {"active"}
        assert {edge.to_time for edge in after} == {deleted_at.to_string()}

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
        widget = await _create_widget(db=db, branch=default_branch, name="delete-rolls-back", serial=700)

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

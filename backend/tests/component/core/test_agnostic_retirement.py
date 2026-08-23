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
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import rebase_branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.node_agnostic_retirement import RetireNodeAgnosticFieldsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode
from infrahub.workers.dependencies import build_cache, build_database, build_workflow

if TYPE_CHECKING:
    from fast_depends import Provider
    from neo4j import Record

    from infrahub.core.query import QueryType
    from infrahub.core.schema.schema_branch import SchemaBranch

from tests.adapters.cache import MemoryCache
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.agnostic_edges import (
    EdgeState,
    attribute_global_edges,
    attribute_owning_edges,
    attribute_vertex_uuid,
    edge_summary,
    existence_edges,
    expected_closed_at,
    global_edges_by_vertex_uuid,
    open_edge_types,
    open_edges,
    pool_reservation_edges,
    relationship_global_edges,
    relationship_vertex_uuid,
    remove_attribute_on_branch,
    to_times,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)

SERIAL_POOL_START = 9001
SERIAL_POOL_END = 9002


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


async def _rebase_branch(
    db: InfrahubDatabase, default_branch: Branch, branch: Branch, dependency_provider: Provider
) -> Branch:
    """Rebase the branch through the real rebase flow, and return its refreshed Branch object.

    The enforcement point under test lives inside the rebase flow's own transaction, so the real flow
    is the only faithful driver. Refreshed, because the rebase moves the branch's fork point and every
    later read through the stale object would still see the pre-rebase window.
    """
    lock.initialize_lock(local_only=True)
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        # Lambdas rather than the bare classes: fast_depends reads the callable's return annotation,
        # and a class used as the factory resolves to `None` and fails its validation.
        dependency_provider.scope(build_workflow, lambda: WorkflowRecorder()),  # noqa: PLW0108
        dependency_provider.scope(build_cache, lambda: MemoryCache()),  # noqa: PLW0108
    ):
        await rebase_branch(branch=branch.name, context=context, send_events=False)
    return await Branch.get_by_name(db=db, name=branch.name)


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
        assert reserved_before == [
            EdgeState(edge_type="IS_RESERVED", branch=GLOBAL_BRANCH_NAME, status="active", to_time=None)
        ]

        deleted_at = Timestamp()
        await _delete(db=db, node_id=holder.id, branch=default_branch, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=holder.id, attribute_name="serial")
        assert edge_summary(after) == expected_closed_at(before, deleted_at)
        assert await pool_reservation_edges(db=db, pool_id=serial_pool.id, identifier=holder.id) == reserved_before, (
            "the reservation is never cleaned up on delete, and does not need to be"
        )
        assert await serial_pool.get_used(db=db, branch=default_branch) == []

        reallocated = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
        await reallocated.new(db=db, name="takes-the-freed-serial", serial={"from_pool": {"id": serial_pool.id}})
        await reallocated.save(db=db)

        assert reallocated.get_attribute(name="serial").value == SERIAL_POOL_START
        assert await serial_pool.get_used(db=db, branch=default_branch) == [SERIAL_POOL_START]


class TestAgnosticRetirementOnRebase:
    """The rebase enforcement point: retention is re-evaluated for the deletions the rebase absorbs.

    The rebase is never the release trigger. Inside its own transaction, once the branch's fork point
    has moved past the base branch's deletions, it re-runs the same predicate the delete point runs
    over the nodes the base-branch diff records as removed, and acts only on the result. Driven
    through the real rebase flow, because that transaction is where the point lives.
    """

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
        """The rebase flow resolves core kinds while it diffs and validates, so the core schema rides along."""
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)

    async def test_rebasing_past_the_deletion_closes_the_field(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """A deletion deferred by an open branch is released when that branch rebases past it.

        The branch forked while the object was live, so the default-branch delete closes nothing.
        Rebasing moves the branch's fork point past the deletion, after which the branch reads the
        object as deleted like everyone else; no branch retains it, and the rebase's re-evaluation
        closes the attribute's and the relationship's global edges at the rebase timestamp.
        """
        gadget = await Node.init(db=db, schema=GADGET_KIND, branch=default_branch)
        await gadget.new(db=db, name="peer-of-the-rebased-past-deletion")
        await gadget.save(db=db)
        widget = await _create_widget(
            db=db, branch=default_branch, name="deleted-then-rebased-past", serial=2400, gadget=gadget
        )
        branch = await create_branch(db=db, branch_name="rebases-past-the-deletion")

        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(attribute_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await _delete(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        ), "the branch still reads the object, so the default-branch delete released nothing"

        rebased = await _rebase_branch(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )
        rebase_at = Timestamp(rebased.get_branched_from())

        assert await NodeManager.get_one(db=db, id=widget.id, branch=rebased) is None, (
            "the rebase carried the deletion into the branch's view"
        )
        attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert edge_summary(attribute_after) == expected_closed_at(attribute_before, rebase_at)
        assert {edge.status for edge in attribute_after} == {"active"}, (
            "retirement is a time-close, never a status tombstone"
        )
        relationship_after = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )
        assert open_edges(relationship_after) == [], (
            "no branch reads both peers as live once the rebase lands, so the relationship goes with it"
        )
        assert to_times(relationship_after) == {rebase_at.to_string()}

    async def test_rebasing_releases_nothing_while_another_branch_retains_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """The rebase re-evaluates and defers: a branch that still reads the object keeps it reserved."""
        widget = await _create_widget(db=db, branch=default_branch, name="retained-through-a-rebase", serial=2500)
        retainer = await create_branch(db=db, branch_name="retains-through-the-rebase")
        branch = await create_branch(db=db, branch_name="rebases-while-another-retains")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await _delete(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        rebased = await _rebase_branch(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )

        assert await NodeManager.get_one(db=db, id=widget.id, branch=rebased) is None, (
            "the rebased branch itself stopped retaining the object"
        )
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        ), "the retaining branch still reads the object, so the rebase released nothing"
        on_retainer = await NodeManager.get_one(db=db, id=widget.id, branch=retainer)
        assert on_retainer is not None
        assert on_retainer.get_attribute(name="serial").value == 2500

    async def test_rebasing_a_branch_that_created_and_deleted_the_object_leaves_no_open_edges(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """A branch-local lifecycle leaves nothing open once the rebase erases its branch-level evidence."""
        branch = await create_branch(db=db, branch_name="creates-and-deletes-then-rebases")
        gadget = await Node.init(db=db, schema=GADGET_KIND, branch=branch)
        await gadget.new(db=db, name="peer-of-the-branch-local-widget")
        await gadget.save(db=db)
        widget = await _create_widget(
            db=db, branch=branch, name="branch-local-then-rebased", serial=2600, gadget=gadget
        )
        attribute_uuid = await attribute_vertex_uuid(db=db, node_id=widget.id, attribute_name="serial")
        relationship_uuid = await relationship_vertex_uuid(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)

        deleted_at = Timestamp()
        await _delete(db=db, node_id=widget.id, branch=branch, at=deleted_at)
        assert open_edges(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == [], (
            "the delete point closed the branch-only object's global edges; the rebase must not reopen or orphan them"
        )

        rebased = await _rebase_branch(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )

        attribute_after = await global_edges_by_vertex_uuid(db=db, vertex_uuid=attribute_uuid)
        assert attribute_after, "the attribute vertex must keep its closed edges, not end up cut loose or edgeless"
        assert open_edges(attribute_after) == []
        assert to_times(attribute_after) == {deleted_at.to_string()}, (
            "the close keeps the delete's own stamp; the rebase had nothing left to do"
        )
        relationship_after = await global_edges_by_vertex_uuid(db=db, vertex_uuid=relationship_uuid)
        assert relationship_after, (
            "the relationship vertex must keep its closed edges, not end up cut loose or edgeless"
        )
        assert open_edges(relationship_after) == []
        assert to_times(relationship_after) == {deleted_at.to_string()}
        assert await NodeManager.get_one(db=db, id=widget.id, branch=rebased) is None
        on_branch_gadget = await NodeManager.get_one(db=db, id=gadget.id, branch=rebased)
        assert on_branch_gadget is not None, "the branch's surviving peer rides through the rebase untouched"

    async def test_a_retirement_failure_rolls_back_the_whole_rebase(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """The re-evaluation shares the rebase's transaction, so its failure takes the rebase down whole.

        A rebase that committed its fork-point move while the retirement failed would leave the branch
        no longer retaining the deletion, with no later enforcement point ever revisiting it.
        """
        widget = await _create_widget(db=db, branch=default_branch, name="rebase-rolls-back", serial=2700)
        branch = await create_branch(db=db, branch_name="rebase-that-rolls-back")
        branched_from_before = (await Branch.get_by_name(db=db, name=branch.name)).get_branched_from()

        await _delete(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        failing_db = FailingRetirementDatabase.from_db(db=db)
        lock.initialize_lock(local_only=True)
        context = InfrahubContext.init(
            branch=default_branch,
            account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
        )
        with (
            dependency_provider.scope(build_database, lambda singleton=True: failing_db),  # noqa: ARG005
            # Lambdas rather than the bare classes: fast_depends reads the callable's return annotation,
            # and a class used as the factory resolves to `None` and fails its validation.
            dependency_provider.scope(build_workflow, lambda: WorkflowRecorder()),  # noqa: PLW0108
            dependency_provider.scope(build_cache, lambda: MemoryCache()),  # noqa: PLW0108
        ):
            with pytest.raises(RetirementFailureError, match=r"^the retirement run could not complete$"):
                await rebase_branch(branch=branch.name, context=context, send_events=False)

        in_db = await Branch.get_by_name(db=db, name=branch.name)
        assert in_db.get_branched_from() == branched_from_before, (
            "the fork point moved even though the retirement inside the same transaction failed"
        )
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        )
        on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=in_db)
        assert on_branch is not None, "the branch keeps retaining the object, which is what the rollback preserves"
        assert on_branch.get_attribute(name="serial").value == 2700

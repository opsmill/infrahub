"""The rebase enforcement point: retention is re-evaluated for the deletions the rebase absorbs.

The rebase is never the release trigger. Inside its own transaction, once the branch's fork point
has moved past the base branch's deletions, it re-runs the same predicate the delete point runs
over the nodes deleted on the base branch within the window the rebase closes, and acts only on the
result. Driven through the real rebase flow, because that transaction is where the point lives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import (
    NodeKindUpdateMigration,
    NodeKindUpdateMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.node_agnostic_retirement import RetireNodeAgnosticFieldsQuery
from infrahub.core.timestamp import Timestamp
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

from tests.component.core.agnostic_retirement.support import (
    FailingRetirementDatabase,
    RetirementFailureError,
    delete_node,
    rebase_branch,
)
from tests.helpers.agnostic_edges import (
    TEST_ACTOR_ID,
    actors_closing_at,
    assert_attribute_retired_at,
    assert_relationship_retired_at,
    attribute_global_edges,
    attribute_vertex_uuid,
    create_widget,
    edge_summary,
    global_edges_by_vertex_uuid,
    node_vertex_count,
    open_active_edges,
    open_edge_types,
    open_edges,
    relationship_global_edges,
    relationship_vertex_uuid,
    to_times,
    values_reachable_over_open_edges,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)

INHERITED_GENERIC = "AgnosticretireInherited"


async def _change_widget_inheritance(db: InfrahubDatabase, branch: Branch) -> None:
    """Add a generic to the widget kind in the graph, leaving a superseded node vertex under every live widget's uuid.

    The kind is unchanged, so the live copy still loads, and it shares the original's field vertices.
    """
    previous_schema = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch, duplicate=False)
    new_schema = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch, duplicate=True)
    new_schema.inherit_from = [INHERITED_GENERIC]

    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=new_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=new_schema.kind, field_name="inherit_from"),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=branch, migration=migration)
    await query.execute(db=db)


class TestAgnosticRetirementOnRebase:
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
        widget = await create_widget(
            db=db, branch=default_branch, name="deleted-then-rebased-past", serial=2400, gadget=gadget
        )
        branch = await create_branch(db=db, branch_name="rebases-past-the-deletion")

        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(attribute_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}
        relationship_before = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        ), "the branch still reads the object, so the default-branch delete released nothing"

        rebased = await rebase_branch(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )
        rebase_at = Timestamp(rebased.get_branched_from())

        assert await NodeManager.get_one(db=db, id=widget.id, branch=rebased) is None, (
            "the rebase carried the deletion into the branch's view"
        )
        attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=attribute_after, before=attribute_before, at=rebase_at, by=TEST_ACTOR_ID)
        relationship_after = await relationship_global_edges(
            db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER
        )
        assert_relationship_retired_at(
            after=relationship_after, before=relationship_before, at=rebase_at, by=TEST_ACTOR_ID
        )

    async def test_rebasing_a_branch_with_changes_of_its_own_past_the_deletion_closes_the_field(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """What the branch itself changed does not narrow the base-branch deletions its rebase releases."""
        widget = await create_widget(db=db, branch=default_branch, name="deleted-under-a-changed-branch", serial=2800)
        branch = await create_branch(db=db, branch_name="changes-then-rebases-past-the-deletion")
        unrelated = await Node.init(db=db, schema=GADGET_KIND, branch=branch)
        await unrelated.new(db=db, name="unrelated-change-on-the-branch")
        await unrelated.save(db=db)
        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        rebased = await rebase_branch(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )
        rebase_at = Timestamp(rebased.get_branched_from())

        assert await NodeManager.get_one(db=db, id=widget.id, branch=rebased) is None
        assert await NodeManager.get_one(db=db, id=unrelated.id, branch=rebased) is not None
        attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert_attribute_retired_at(after=attribute_after, before=attribute_before, at=rebase_at, by=TEST_ACTOR_ID)

    async def test_rebasing_past_the_deletion_of_a_node_with_a_superseded_vertex_closes_the_field(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """A node whose inheritance changed before the fork is released like any other once rebased past."""
        widget = await create_widget(db=db, branch=default_branch, name="inheritance-changed-then-deleted", serial=2900)
        await _change_widget_inheritance(db=db, branch=default_branch)
        assert await node_vertex_count(db=db, node_id=widget.id) == 2, (
            "the inheritance change is expected to leave a superseded node vertex sharing the uuid"
        )
        branch = await create_branch(db=db, branch_name="rebases-past-a-superseded-vertex")

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert await values_reachable_over_open_edges(db=db, node_id=widget.id, attribute_name="serial") == [2900], (
            "the branch still reads the object, so the default-branch delete released nothing"
        )

        rebased = await rebase_branch(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )
        rebase_at = Timestamp(rebased.get_branched_from())

        assert await NodeManager.get_one(db=db, id=widget.id, branch=rebased) is None
        attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_active_edges(attribute_after) == []
        closed_by_the_rebase = [edge for edge in attribute_after if edge.to_time == rebase_at.to_string()]
        assert sorted(edge.edge_type for edge in closed_by_the_rebase) == sorted(
            edge.edge_type for edge in open_active_edges(attribute_before)
        )
        assert actors_closing_at(attribute_after, at=rebase_at) == {TEST_ACTOR_ID}

    async def test_rebasing_past_an_inheritance_change_releases_nothing(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """The vertex an inheritance change supersedes is deleted, but the node lives on and keeps its fields."""
        widget = await create_widget(db=db, branch=default_branch, name="inheritance-changed-and-kept", serial=3000)
        branch = await create_branch(db=db, branch_name="rebases-past-an-inheritance-change")
        await _change_widget_inheritance(db=db, branch=default_branch)
        assert await node_vertex_count(db=db, node_id=widget.id) == 2, (
            "the inheritance change is expected to leave a superseded node vertex sharing the uuid"
        )
        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        counting_db = CountingInfrahubDatabase.from_db(db=db)
        rebased = await rebase_branch(
            db=counting_db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )

        assert counting_db.count_for(RetireNodeAgnosticFieldsQuery.name) == 1, (
            "the superseded vertex's deletion falls in the rebased window, so the node is re-evaluated"
        )
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        )
        on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=rebased)
        assert on_branch is not None
        assert on_branch.get_attribute(name="serial").value == 3000

    async def test_rebasing_releases_nothing_while_another_branch_retains_the_object(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        agnostic_schema: None,
        dependency_provider: Provider,
    ) -> None:
        """The rebase re-evaluates and defers: a branch that still reads the object keeps it reserved."""
        widget = await create_widget(db=db, branch=default_branch, name="retained-through-a-rebase", serial=2500)
        retainer = await create_branch(db=db, branch_name="retains-through-the-rebase")
        branch = await create_branch(db=db, branch_name="rebases-while-another-retains")

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        rebased = await rebase_branch(
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
        widget = await create_widget(db=db, branch=branch, name="branch-local-then-rebased", serial=2600, gadget=gadget)
        attribute_uuid = attribute_vertex_uuid(node=widget, attribute_name="serial")
        relationship_uuid = relationship_vertex_uuid(node=widget, relationship_name="gadget")

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=branch, at=deleted_at)
        assert open_edges(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == [], (
            "the delete point closed the branch-only object's global edges; the rebase must not reopen or orphan them"
        )

        rebased = await rebase_branch(
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
        widget = await create_widget(db=db, branch=default_branch, name="rebase-rolls-back", serial=2700)
        branch = await create_branch(db=db, branch_name="rebase-that-rolls-back")
        branched_from_before = (await Branch.get_by_name(db=db, name=branch.name)).get_branched_from()

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        failing_db = FailingRetirementDatabase.from_db(db=db)
        with pytest.raises(RetirementFailureError, match=r"^the retirement run could not complete$"):
            await rebase_branch(
                db=failing_db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
            )

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

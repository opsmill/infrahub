"""The rebase enforcement point: retention is re-evaluated for the deletions the rebase absorbs.

The rebase is never the release trigger. Inside its own transaction, once the branch's fork point
has moved past the base branch's deletions, it re-runs the same predicate the delete point runs
over the nodes the base-branch diff records as removed, and acts only on the result. Driven
through the real rebase flow, because that transaction is where the point lives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import rebase_branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.workers.dependencies import build_cache, build_database, build_workflow

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

from tests.adapters.cache import MemoryCache
from tests.adapters.workflow import WorkflowRecorder
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
    attribute_vertex_uuid,
    create_widget,
    edge_summary,
    global_edges_by_vertex_uuid,
    open_edge_types,
    open_edges,
    relationship_global_edges,
    relationship_vertex_uuid,
    to_times,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
)


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
        account=AccountSession(account_id=TEST_ACTOR_ID, auth_type=AuthType.NONE),
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

        rebased = await _rebase_branch(
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
        widget = await create_widget(db=db, branch=branch, name="branch-local-then-rebased", serial=2600, gadget=gadget)
        attribute_uuid = attribute_vertex_uuid(node=widget, attribute_name="serial")
        relationship_uuid = relationship_vertex_uuid(node=widget, relationship_name="gadget")

        deleted_at = Timestamp()
        await delete_node(db=db, node_id=widget.id, branch=branch, at=deleted_at)
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
        widget = await create_widget(db=db, branch=default_branch, name="rebase-rolls-back", serial=2700)
        branch = await create_branch(db=db, branch_name="rebase-that-rolls-back")
        branched_from_before = (await Branch.get_by_name(db=db, name=branch.name)).get_branched_from()

        await delete_node(db=db, node_id=widget.id, branch=default_branch, at=Timestamp())
        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        failing_db = FailingRetirementDatabase.from_db(db=db)
        with pytest.raises(RetirementFailureError, match=r"^the retirement run could not complete$"):
            await _rebase_branch(
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

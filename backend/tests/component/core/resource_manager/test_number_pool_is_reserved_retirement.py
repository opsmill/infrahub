"""A number pool's IS_RESERVED edge is closed once no branch can reach the attribute it points at.

The IS_RESERVED edge is always written on the global branch, so none of the branch-scoped writes
that end an object ever reach it. The triggers tested here are deleting the object, merging or
rebasing a delete, and deleting a branch.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, InfrahubKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from tests.component.core.agnostic_retirement.test_on_rebase import _rebase_branch
from tests.component.core.resource_manager.conftest import (
    SERIAL_ATTRIBUTE_NAME,
    SERIAL_POOL_START,
    delete_branch,
    pooled_holder,
)
from tests.helpers.agnostic_edges import (
    TEST_ACTOR_ID,
    EdgeState,
    IsReservedEdge,
    attribute_edges,
    attributes_holding_only_is_reserved_edges,
    is_reserved_edge_on,
    single_is_reserved_edge,
)
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, AGNOSTIC_WIDGET, WIDGET_KIND

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema import NodeSchema, SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

AWARE_WIDGET_KIND = "AgnosticretireAwarewidget"

POOL_END = SERIAL_POOL_START + 99
"""Wide enough for every object a class allocates, since the pools outlive each test."""


def _aware_widget() -> NodeSchema:
    """The widget as its own kind with `serial` branch-aware, so both branch supports can be registered at once."""
    widget = deepcopy(AGNOSTIC_WIDGET)
    widget.name = "Awarewidget"
    widget.get_attribute(name=SERIAL_ATTRIBUTE_NAME).branch = BranchSupportType.AWARE
    widget.get_relationship(name="gadget").identifier = "agnosticretire_awarewidget__agnosticretire_gadget"
    return widget


def _pooled_schema() -> SchemaRoot:
    schema = deepcopy(AGNOSTIC_RETIREMENT_SCHEMA)
    schema.nodes.append(_aware_widget())
    return schema


@dataclass
class SupportCase:
    name: str
    branch_support: BranchSupportType
    kind: str


SUPPORT_CASES = [
    SupportCase(name="branch-aware", branch_support=BranchSupportType.AWARE, kind=AWARE_WIDGET_KIND),
    SupportCase(name="branch-agnostic", branch_support=BranchSupportType.AGNOSTIC, kind=WIDGET_KIND),
]


async def _make_pool(db: InfrahubDatabase, kind: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=f"serial-pool-{kind}",
        node=kind,
        node_attribute=SERIAL_ATTRIBUTE_NAME,
        start_range=SERIAL_POOL_START,
        end_range=POOL_END,
    )
    await pool.save(db=db)
    return pool


@pytest.fixture(scope="class")
async def pools(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    register_core_models_schema_scope_class: SchemaBranch,
) -> dict[str, CoreNumberPool]:
    """Both widget kinds registered once for the class, each with its own pool, keyed by kind."""
    registry.schema.register_schema(schema=_pooled_schema(), branch=default_branch_scope_class.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    return {kind: await _make_pool(db=db, kind=kind) for kind in (AWARE_WIDGET_KIND, WIDGET_KIND)}


def serial_of(node: Node) -> int:
    value = node.get_attribute(name=SERIAL_ATTRIBUTE_NAME).value
    assert isinstance(value, int)
    return value


async def is_reserved_edge_naming(db: InfrahubDatabase, pool_id: str, node_id: str) -> IsReservedEdge:
    """The state of the pool's active IS_RESERVED edge for this object.

    Found by the object's identifier on the edge, so it still finds the edge once the branch delete
    has removed the object's own edges to the attribute.
    """
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $pool_id})-[is_reserved:IS_RESERVED]->(:Attribute)
        WHERE is_reserved.identifier = $node_id AND is_reserved.status = "active"
        RETURN properties(is_reserved) AS is_reserved
        """,
        params={"pool_id": pool_id, "node_id": node_id},
    )
    return single_is_reserved_edge([dict(result["is_reserved"]) for result in results])


async def branch_value_edges(db: InfrahubDatabase, node_id: str, attribute_name: str, branch_name: str) -> int:
    """How many open HAS_VALUE edges this branch wrote on the object's named attribute vertex."""
    results = await db.execute_query(
        query="""
        MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
        WITH DISTINCT a
        MATCH (a)-[e:HAS_VALUE]->()
        WHERE e.branch = $branch_name AND e.status = "active" AND e.to IS NULL
        RETURN count(e) AS nbr
        """,
        params={"node_id": node_id, "attribute_name": attribute_name, "branch_name": branch_name},
    )
    return results[0]["nbr"]


async def other_edges_on(db: InfrahubDatabase, node_id: str, attribute_name: str) -> set[EdgeState]:
    """Every edge on the object's named attribute vertex other than an IS_RESERVED edge, as stored."""
    edges = await attribute_edges(db=db, node_id=node_id, attribute_name=attribute_name)
    return {edge for edge in edges if edge.edge_type != "IS_RESERVED"}


async def merge_branch(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> None:
    """Merge the branch's graph into the default branch, the way the merge flow drives it."""
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_merger.merge_graph(at=Timestamp(), user_id=TEST_ACTOR_ID)


class TestObjectDelete:
    @pytest.mark.parametrize("case", SUPPORT_CASES, ids=lambda case: case.name)
    async def test_deleting_the_object_closes_its_is_reserved_edge(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        case: SupportCase,
    ) -> None:
        pool = pools[case.kind]
        holder = await pooled_holder(
            db=db, branch=default_branch_scope_class, kind=case.kind, pool=pool, name=f"deleted-{case.name}"
        )
        number = serial_of(holder)

        await holder.delete(db=db, at=Timestamp())

        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.CLOSED
        ), "no branch reaches the deleted object, so its IS_RESERVED edge must be closed"
        assert number not in await pool.get_used(db=db, branch=default_branch_scope_class)

    @pytest.mark.parametrize("case", SUPPORT_CASES, ids=lambda case: case.name)
    async def test_the_pool_still_counts_the_number_an_older_branch_holds(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        case: SupportCase,
    ) -> None:
        pool = pools[case.kind]
        holder = await pooled_holder(
            db=db, branch=default_branch_scope_class, kind=case.kind, pool=pool, name=f"counted-for-older-{case.name}"
        )
        number = serial_of(holder)
        older = await create_branch(db=db, branch_name=f"older-still-counts-{case.name}")

        await holder.delete(db=db, at=Timestamp())

        assert await NodeManager.get_one(db=db, id=holder.id, branch=older) is not None
        assert number in await pool.get_used(db=db, branch=older), (
            "the pool still accounts for the number the older branch holds"
        )

    @pytest.mark.parametrize("case", SUPPORT_CASES, ids=lambda case: case.name)
    async def test_the_is_reserved_edge_stays_open_until_the_last_older_branch_is_deleted(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        case: SupportCase,
    ) -> None:
        pool = pools[case.kind]
        holder = await pooled_holder(
            db=db, branch=default_branch_scope_class, kind=case.kind, pool=pool, name=f"held-by-two-{case.name}"
        )
        first = await create_branch(db=db, branch_name=f"first-older-{case.name}")
        second = await create_branch(db=db, branch_name=f"second-older-{case.name}")

        await holder.delete(db=db, at=Timestamp())
        await delete_branch(db=db, branch=first)

        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.OPEN
        ), "the second older branch still holds the object through its fork point"
        assert await NodeManager.get_one(db=db, id=holder.id, branch=second) is not None

        await delete_branch(db=db, branch=second)

        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.CLOSED
        ), "deleting the last branch that reached the object must close its IS_RESERVED edge"

    async def test_deleting_a_branch_that_updated_the_attribute_keeps_the_is_reserved_edge_open(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pools: dict[str, CoreNumberPool]
    ) -> None:
        """The branch writes its own edges on a live vertex, so its delete sweeps that vertex."""
        pool = pools[AWARE_WIDGET_KIND]
        holder = await pooled_holder(
            db=db, branch=default_branch_scope_class, kind=AWARE_WIDGET_KIND, pool=pool, name="updated-on-a-branch"
        )
        number = serial_of(holder)
        updated = await pool.get_free(db=db, branch=default_branch_scope_class)
        assert isinstance(updated, int), "the update moves to a number no other object holds"
        branch = await create_branch(db=db, branch_name="updates-the-pooled-attribute")
        on_branch = await NodeManager.get_one(db=db, id=holder.id, branch=branch, raise_on_error=True)
        on_branch.get_attribute(name=SERIAL_ATTRIBUTE_NAME).value = updated
        await on_branch.save(db=db)
        assert (
            await branch_value_edges(
                db=db, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME, branch_name=branch.name
            )
            == 1
        ), "the update must write the branch's own value edge on the shared vertex"

        await delete_branch(db=db, branch=branch)

        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.OPEN
        ), "the default branch still holds the object"
        used = await pool.get_used(db=db, branch=default_branch_scope_class)
        assert number in used
        assert updated not in used, "the number only the deleted branch held stops counting as used"

    @pytest.mark.parametrize("case", SUPPORT_CASES, ids=lambda case: case.name)
    async def test_deleting_the_branch_an_object_was_created_on_deletes_its_is_reserved_edge(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        case: SupportCase,
    ) -> None:
        pool = pools[case.kind]
        branch = await create_branch(db=db, branch_name=f"creates-the-pooled-object-{case.name}")
        holder = await pooled_holder(
            db=db, branch=branch, kind=case.kind, pool=pool, name=f"created-on-a-branch-{case.name}"
        )
        number = serial_of(holder)

        await delete_branch(db=db, branch=branch)

        # Every edge of the attribute vertex belongs to the deleted branch apart from the IS_RESERVED edge,
        # so the vertex goes with the branch and the IS_RESERVED edge is deleted with it, whatever its
        # branch support.
        assert await is_reserved_edge_naming(db=db, pool_id=pool.id, node_id=holder.id) == IsReservedEdge.ABSENT, (
            "only the deleted branch held the object, so its IS_RESERVED edge must go with its attribute"
        )
        assert await attributes_holding_only_is_reserved_edges(db=db, pool_id=pool.id) == 0, (
            "no pool may be left pointing at an attribute with nothing else linked to it"
        )
        assert number not in await pool.get_used(db=db, branch=default_branch_scope_class)

    @pytest.mark.parametrize("case", SUPPORT_CASES, ids=lambda case: case.name)
    async def test_rebasing_past_a_default_branch_delete_closes_the_is_reserved_edge(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        case: SupportCase,
        dependency_provider: Provider,
    ) -> None:
        pool = pools[case.kind]
        holder = await pooled_holder(
            db=db, branch=default_branch_scope_class, kind=case.kind, pool=pool, name=f"rebased-past-{case.name}"
        )
        branch = await create_branch(db=db, branch_name=f"rebases-past-the-delete-{case.name}")

        await holder.delete(db=db, at=Timestamp())
        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.OPEN
        ), "the branch still holds the object through its fork point"

        rebased = await _rebase_branch(
            db=db, default_branch=default_branch_scope_class, branch=branch, dependency_provider=dependency_provider
        )

        assert await NodeManager.get_one(db=db, id=holder.id, branch=rebased) is None, (
            "the rebase carried the delete into the branch's view"
        )
        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.CLOSED
        ), "once the branch rebases past the delete, no branch reaches the object"

    @pytest.mark.parametrize("case", SUPPORT_CASES, ids=lambda case: case.name)
    async def test_merging_a_delete_closes_the_is_reserved_edge(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        case: SupportCase,
    ) -> None:
        pool = pools[case.kind]
        holder = await pooled_holder(
            db=db, branch=default_branch_scope_class, kind=case.kind, pool=pool, name=f"deleted-by-merge-{case.name}"
        )
        branch = await create_branch(db=db, branch_name=f"deletes-then-merges-{case.name}")

        on_branch = await NodeManager.get_one(db=db, id=holder.id, branch=branch, raise_on_error=True)
        await on_branch.delete(db=db, at=Timestamp())
        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.OPEN
        ), "the default branch still holds the object"

        await merge_branch(db=db, default_branch=default_branch_scope_class, branch=branch)

        assert await NodeManager.get_one(db=db, id=holder.id, branch=default_branch_scope_class) is None
        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.CLOSED
        ), "once the merge carries the delete over, no branch reaches the object"


class TestOnlyTheIsReservedEdgeIsClosed:
    """On a branch-aware attribute the IS_RESERVED edge is the only global edge the retirement closes.

    The retirement closes every open global edge on an unretained field. Each test holds the attribute
    unretained, snapshots its other edges, runs one retirement trigger and checks none of them moved.
    """

    async def _deleted_with_an_older_branch(
        self, db: InfrahubDatabase, default_branch: Branch, pool: CoreNumberPool, name: str
    ) -> tuple[Node, Branch, set[EdgeState]]:
        holder = await pooled_holder(db=db, branch=default_branch, kind=AWARE_WIDGET_KIND, pool=pool, name=name)
        older = await create_branch(db=db, branch_name=f"predates-the-delete-of-{name}")
        await holder.delete(db=db, at=Timestamp())
        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.OPEN
        ), "the older branch still holds the object through its fork point"

        before = await other_edges_on(db=db, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
        assert before, "the attribute vertex must carry edges besides the IS_RESERVED edge"
        assert all(edge.branch != GLOBAL_BRANCH_NAME for edge in before), (
            "a branch-aware attribute carries no global edge other than the IS_RESERVED edge"
        )
        return holder, older, before

    async def test_branch_retirement_leaves_the_other_edges_untouched(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pools: dict[str, CoreNumberPool]
    ) -> None:
        pool = pools[AWARE_WIDGET_KIND]
        holder, older, before = await self._deleted_with_an_older_branch(
            db=db, default_branch=default_branch_scope_class, pool=pool, name="retired-by-branch-delete"
        )

        await delete_branch(db=db, branch=older)

        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.CLOSED
        )
        assert await other_edges_on(db=db, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME) == before, (
            "the older branch wrote nothing on the vertex, so its delete must leave every other edge as it was"
        )

    async def test_node_retirement_leaves_the_other_edges_untouched(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pools: dict[str, CoreNumberPool],
        dependency_provider: Provider,
    ) -> None:
        """Rebasing the older branch past the delete runs the node retirement over the deleted object."""
        pool = pools[AWARE_WIDGET_KIND]
        holder, older, before = await self._deleted_with_an_older_branch(
            db=db, default_branch=default_branch_scope_class, pool=pool, name="retired-by-a-rebase"
        )

        await _rebase_branch(
            db=db, default_branch=default_branch_scope_class, branch=older, dependency_provider=dependency_provider
        )

        assert (
            await is_reserved_edge_on(db=db, pool_id=pool.id, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME)
            == IsReservedEdge.CLOSED
        )
        assert await other_edges_on(db=db, node_id=holder.id, attribute_name=SERIAL_ATTRIBUTE_NAME) == before, (
            "the older branch wrote nothing on the vertex, so the rebase must leave every other edge as it was"
        )

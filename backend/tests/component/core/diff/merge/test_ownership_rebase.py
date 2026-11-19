from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import DiffAction
from infrahub.core.initialization import create_branch
from infrahub.core.ownership.queries import NoOwnerVertexCreateQuery
from tests.helpers.ownership import (
    OwnerDataset,
    read_owners,
    set_owners,
)

from ._ownership import count_active_holder_edges, has_owner_change, holder_edges, merge, owner_property, update_diff

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase


async def test_owner_change_of_a_branch_stays_in_the_diff_after_a_rebase(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    rack_id = dataset.ids["rack-a"]
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="branch-change")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("security",)))
    await set_owners(db=db, branch=default_branch, node_id=rack_id, owner_ids=dataset.owners(("network-emea",)))
    assert await read_owners(db=db, branch=branch, node_id=rack_id) is None

    await branch.rebase(db=db)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == dataset.owners(("security",))
    assert await read_owners(db=db, branch=branch, node_id=rack_id) == dataset.owners(("network-emea",))
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(("dc-emea",))
    assert await read_owners(db=db, branch=default_branch, node_id=rack_id) == dataset.owners(("network-emea",))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(("dc-emea",)),
        dataset.owner_list(("security",)),
        DiffAction.UPDATED,
    )
    assert rack_id not in {node.uuid for node in diff.nodes}
    await merge(db=db, branch=branch)
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(("security",))
    assert await read_owners(db=db, branch=default_branch, node_id=rack_id) == dataset.owners(("network-emea",))


async def test_rebase_after_both_branches_set_the_same_owners(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    owner_ids = dataset.owners(("network-emea", "security"))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="same-owners")
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=owner_ids)
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=owner_ids)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert diff.get_all_conflicts() == {}

    await branch.rebase(db=db)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == owner_ids
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert not has_owner_change(diff=diff)
    await merge(db=db, branch=branch)
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == owner_ids
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=tenant_id) == len(owner_ids)


async def test_rebase_keeps_the_new_global_owners_of_a_branch_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    group_id = dataset.ids["security"]
    await set_owners(db=db, branch=default_branch, node_id=group_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="global-owner-rebase")
    await set_owners(db=db, branch=default_branch, node_id=group_id, owner_ids=dataset.owners(("network-emea",)))
    await set_owners(db=db, branch=branch, node_id=dataset.ids["tenant-a"], owner_ids=dataset.owners(("dc-emea",)))
    edges = await holder_edges(db=db, node_id=group_id)

    await branch.rebase(db=db)

    assert await holder_edges(db=db, node_id=group_id) == edges
    assert await read_owners(db=db, branch=branch, node_id=group_id) == dataset.owners(("network-emea",))
    assert await read_owners(db=db, branch=branch, node_id=dataset.ids["tenant-a"]) == dataset.owners(("dc-emea",))


async def _count_no_owner_vertices(db: InfrahubDatabase) -> int:
    results = await db.execute_query(query="MATCH (n:NoOwner) RETURN count(n) AS total")
    return results[0]["total"]


async def test_rebase_keeps_the_no_owner_vertex_when_the_branch_closed_its_only_edge(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await (await NoOwnerVertexCreateQuery.init(db=db)).execute(db=db)
    branch = await create_branch(db=db, branch_name="no-owner-closed")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=())
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("security",)))

    await branch.rebase(db=db)

    assert await _count_no_owner_vertices(db=db) == 1


async def test_branch_delete_keeps_the_no_owner_vertex_when_the_branch_held_its_only_edge(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    await (await NoOwnerVertexCreateQuery.init(db=db)).execute(db=db)
    branch = await create_branch(db=db, branch_name="no-owner-deleted")
    await set_owners(db=db, branch=branch, node_id=dataset.ids["tenant-a"], owner_ids=())

    await BranchDataDeleter(db=db, batch_size=5).delete(branch=branch)

    assert await _count_no_owner_vertices(db=db) == 1

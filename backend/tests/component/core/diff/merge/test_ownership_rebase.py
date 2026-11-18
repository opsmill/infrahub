from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.constants import DiffAction
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.ownership.queries import NoOwnerVertexCreateQuery
from infrahub.exceptions import ValidationError

from ._ownership import (
    OWNERS_FIELD,
    OwnerDataset,
    count_active_owner_edges,
    has_owner_change,
    load_owner_dataset,
    merge,
    owner_edges,
    owner_property,
    read_owners,
    rebase_with_conflict_check,
    set_owners,
    update_diff,
)

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder


@pytest.fixture
async def dataset(db: InfrahubDatabase, default_branch: Branch) -> OwnerDataset:
    return await load_owner_dataset(db=db, default_branch=default_branch)


async def test_owner_change_of_a_branch_stays_in_the_diff_after_a_rebase(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="branch-change")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("security",)))

    await branch.rebase(db=db)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == dataset.owners(("security",))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(("dc-emea",)),
        dataset.owner_list(("security",)),
        DiffAction.UPDATED,
    )
    await merge(db=db, branch=branch)
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(("security",))


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
    assert await count_active_owner_edges(db=db, branch=default_branch, node_id=tenant_id) == len(owner_ids)


async def test_rebase_after_both_branches_set_different_owners(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    dependency_provider: Provider,
    memory_cache: MemoryCache,
    workflow_recorder: WorkflowRecorder,
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    default_branch_owners = dataset.owners(("network-emea",))
    branch_owners = dataset.owners(("security",))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="different-owners")
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=default_branch_owners)
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=branch_owners)
    conflict_path = f"data/{tenant_id}/{OWNERS_FIELD}/property/HAS_OWNER"
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert list(diff.get_all_conflicts()) == [conflict_path]
    message = f"Update the data so that both branches agree on these conflicts: {conflict_path}."
    with pytest.raises(ValidationError, match=f"{re.escape(message)}$"):
        await rebase_with_conflict_check(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )
    assert (await Branch.get_by_name(db=db, name=branch.name)).branched_from == branch.branched_from
    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == branch_owners
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == default_branch_owners

    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=default_branch_owners)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert diff.get_all_conflicts() == {}
    await branch.rebase(db=db)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == default_branch_owners
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=branch_owners)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value, owners.conflict) == (
        dataset.owner_list(("network-emea",)),
        dataset.owner_list(("security",)),
        None,
    )
    await merge(db=db, branch=branch)
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == branch_owners


@pytest.mark.parametrize(
    ("selection", "merged_owners"),
    [
        pytest.param(ConflictSelection.DIFF_BRANCH, ("dc-emea", "security"), id="second_branch_selected"),
        pytest.param(ConflictSelection.BASE_BRANCH, ("dc-emea", "network-emea"), id="default_branch_selected"),
    ],
)
async def test_second_merged_branch_with_other_owners_gives_one_owner_state(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    selection: ConflictSelection,
    merged_owners: tuple[str, ...],
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    first_branch = await create_branch(db=db, branch_name="first-branch")
    second_branch = await create_branch(db=db, branch_name="second-branch")
    first_owners, second_owners = ("dc-emea", "network-emea"), ("dc-emea", "security")
    await set_owners(db=db, branch=first_branch, node_id=tenant_id, owner_ids=dataset.owners(first_owners))
    await set_owners(db=db, branch=second_branch, node_id=tenant_id, owner_ids=dataset.owners(second_owners))
    await update_diff(db=db, default_branch=default_branch, branch=first_branch, diff_repository=diff_repository)
    await merge(db=db, branch=first_branch)
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(first_owners)
    assert await read_owners(db=db, branch=second_branch, node_id=tenant_id) == dataset.owners(second_owners)

    diff = await update_diff(
        db=db, default_branch=default_branch, branch=second_branch, diff_repository=diff_repository
    )
    conflict = owner_property(diff=diff, node_id=tenant_id).conflict
    assert conflict is not None
    assert (conflict.base_branch_value, conflict.diff_branch_value) == (
        dataset.owner_list(first_owners),
        dataset.owner_list(second_owners),
    )
    await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)
    await merge(db=db, branch=second_branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(merged_owners)
    assert await count_active_owner_edges(db=db, branch=default_branch, node_id=tenant_id) == len(merged_owners)


async def test_second_merged_branch_with_the_same_first_owners_adds_no_owner_edge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    owner_ids = dataset.owners(("dc-emea", "network-emea"))
    first_branch = await create_branch(db=db, branch_name="first-branch")
    second_branch = await create_branch(db=db, branch_name="second-branch")
    await set_owners(db=db, branch=first_branch, node_id=tenant_id, owner_ids=owner_ids)
    await set_owners(db=db, branch=second_branch, node_id=tenant_id, owner_ids=owner_ids)
    await update_diff(db=db, default_branch=default_branch, branch=first_branch, diff_repository=diff_repository)
    await merge(db=db, branch=first_branch)

    diff = await update_diff(
        db=db, default_branch=default_branch, branch=second_branch, diff_repository=diff_repository
    )
    assert diff.get_all_conflicts() == {}
    await merge(db=db, branch=second_branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == owner_ids
    assert await count_active_owner_edges(db=db, branch=default_branch, node_id=tenant_id) == len(owner_ids)


async def test_rebase_keeps_the_new_global_owners_of_a_branch_agnostic_node(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    group_id = dataset.ids["security"]
    await set_owners(db=db, branch=default_branch, node_id=group_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="global-owner-rebase")
    await set_owners(db=db, branch=default_branch, node_id=group_id, owner_ids=dataset.owners(("network-emea",)))
    await set_owners(db=db, branch=branch, node_id=dataset.ids["tenant-a"], owner_ids=dataset.owners(("dc-emea",)))
    edges = await owner_edges(db=db, node_id=group_id)

    await branch.rebase(db=db)

    assert await owner_edges(db=db, node_id=group_id) == edges
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

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.changelog.builder import build_diff_changelog_collector
from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.ownership.models import NODE_SOURCES_HOLDER
from infrahub.database.validation import verify_graph

from ..get_one_node import get_one_diff_node
from ._ownership import SOURCES_FIELD, OwnerDataset, load_owner_dataset, merge, read_owners, set_owners, update_diff

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffProperty, EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def dataset(db: InfrahubDatabase, default_branch: Branch) -> OwnerDataset:
    """The account groups of the data set are the sources of the tests."""
    return await load_owner_dataset(db=db, default_branch=default_branch)


async def _set_sources(db: InfrahubDatabase, branch: Branch, node_id: str, source_ids: tuple[str, ...] | None) -> None:
    await set_owners(db=db, branch=branch, node_id=node_id, owner_ids=source_ids, holder=NODE_SOURCES_HOLDER)


async def _read_sources(db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[str, ...] | None:
    return await read_owners(db=db, branch=branch, node_id=node_id, holder=NODE_SOURCES_HOLDER)


def _sources_property(diff: EnrichedDiffRoot, node_id: str) -> EnrichedDiffProperty:
    node = get_one_diff_node(diff_root=diff, node_uuid=node_id)
    return node.get_attribute(name=SOURCES_FIELD).get_property(property_type=DatabaseEdgeType.HAS_SOURCE)


async def _count_active_source_edges(db: InfrahubDatabase, branch: Branch, node_id: str) -> int:
    query = """
    MATCH (n:Node {uuid: $node_id})-[r:HAS_SOURCE]->()
    WHERE r.branch = $branch_name AND r.status = "active" AND r.to IS NULL
    RETURN count(r) AS total
    """
    results = await db.execute_query(query=query, params={"node_id": node_id, "branch_name": branch.name})
    return results[0]["total"]


async def test_two_sources_set_on_a_branch_show_on_the_default_branch_after_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    sources = dataset.owners(("dc-emea", "network-emea"))
    owners = dataset.owners(("dc-emea",))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=owners)
    branch = await create_branch(db=db, branch_name="sources-merge")

    await _set_sources(db=db, branch=branch, node_id=tenant_id, source_ids=sources)

    assert await _read_sources(db=db, branch=branch, node_id=tenant_id) == sources
    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) is None
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    changed = _sources_property(diff=diff, node_id=tenant_id)
    assert (changed.previous_value, changed.new_value, changed.action) == (
        None,
        dataset.owner_list(("dc-emea", "network-emea")),
        DiffAction.ADDED,
    )
    assert changed.new_label == dataset.owner_labels(("dc-emea", "network-emea"))
    assert [attribute.name for attribute in get_one_diff_node(diff_root=diff, node_uuid=tenant_id).attributes] == [
        SOURCES_FIELD
    ]

    await merge(db=db, branch=branch)

    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) == sources
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == owners
    await verify_graph(db=db)


async def test_source_removed_on_a_branch_is_removed_by_the_merge_with_its_changelog(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await _set_sources(
        db=db, branch=default_branch, node_id=tenant_id, source_ids=dataset.owners(("dc-emea", "network-emea"))
    )
    branch = await create_branch(db=db, branch_name="source-removed")
    await _set_sources(db=db, branch=branch, node_id=tenant_id, source_ids=dataset.owners(("network-emea",)))

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    await merge(db=db, branch=branch)
    changelogs = await build_diff_changelog_collector(diff=diff, db=db, branch=default_branch).collect_changelogs()

    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(("network-emea",))
    assert await _count_active_source_edges(db=db, branch=default_branch, node_id=tenant_id) == 1
    assert [(action, changelog.node_id) for action, changelog in changelogs] == [(DiffAction.UPDATED, tenant_id)]
    assert changelogs[0][1].model_dump()["attributes"] == {
        SOURCES_FIELD: {
            "name": SOURCES_FIELD,
            "kind": "List",
            "value": dataset.owner_list(("network-emea",)),
            "value_previous": dataset.owner_list(("dc-emea", "network-emea")),
            "properties": {},
            "value_update_status": DiffAction.UPDATED,
        }
    }
    await verify_graph(db=db)


@pytest.mark.parametrize(
    ("selection", "merged_sources"),
    [
        pytest.param(ConflictSelection.DIFF_BRANCH, ("security",), id="branch_selected"),
        pytest.param(ConflictSelection.BASE_BRANCH, ("network-emea",), id="default_branch_selected"),
    ],
)
async def test_different_sources_on_both_branches_conflict(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    selection: ConflictSelection,
    merged_sources: tuple[str, ...],
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await _set_sources(db=db, branch=default_branch, node_id=tenant_id, source_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="sources-conflict")
    await _set_sources(db=db, branch=default_branch, node_id=tenant_id, source_ids=dataset.owners(("network-emea",)))
    await _set_sources(db=db, branch=branch, node_id=tenant_id, source_ids=dataset.owners(("security",)))

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    assert list(diff.get_all_conflicts()) == [f"data/{tenant_id}/{SOURCES_FIELD}/property/HAS_SOURCE"]
    conflict = _sources_property(diff=diff, node_id=tenant_id).conflict
    assert conflict is not None
    assert (conflict.base_branch_value, conflict.diff_branch_value) == (
        dataset.owner_list(("network-emea",)),
        dataset.owner_list(("security",)),
    )
    await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)
    await merge(db=db, branch=branch)

    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(merged_sources)
    assert await _count_active_source_edges(db=db, branch=default_branch, node_id=tenant_id) == 1


async def test_merge_closes_the_sources_of_a_node_that_the_branch_deleted(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    device_id = dataset.ids["device-a"]
    await _set_sources(db=db, branch=default_branch, node_id=device_id, source_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="sourced-node-deleted")
    # The branch does not read these sources, so its delete does not close them.
    await _set_sources(
        db=db, branch=default_branch, node_id=device_id, source_ids=dataset.owners(("network-emea", "security"))
    )
    device = await NodeManager.get_one(db=db, branch=branch, id=device_id, raise_on_error=True)
    await device.delete(db=db)
    await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert await _count_active_source_edges(db=db, branch=default_branch, node_id=device_id) == 2

    await merge(db=db, branch=branch)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=device_id) is None
    assert await _count_active_source_edges(db=db, branch=default_branch, node_id=device_id) == 0


async def test_delete_of_a_node_with_a_source_on_an_attribute_closes_the_sources_of_the_node(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    device_id = dataset.ids["device-a"]
    await _set_sources(db=db, branch=default_branch, node_id=device_id, source_ids=dataset.owners(("dc-emea",)))
    device = await NodeManager.get_one(db=db, branch=default_branch, id=device_id, raise_on_error=True)
    device.name.source = dataset.ids["dc-emea"]
    await device.save(db=db)

    await device.delete(db=db)

    assert await _count_active_source_edges(db=db, branch=default_branch, node_id=device_id) == 0
    await verify_graph(db=db)

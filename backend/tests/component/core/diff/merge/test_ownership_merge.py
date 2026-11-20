from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core import registry
from infrahub.core.changelog.builder import build_diff_changelog_collector
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, DiffAction, InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.field_specifiers_map import NodeFieldSpecifierMap
from infrahub.core.diff.model.path import ConflictSelection, DiffNode, DiffRoot
from infrahub.core.diff.ownership_differ import OwnerDiffRequest, OwnershipDiffer
from infrahub.core.diff.query.ownership import DiffOwnerHoldersQuery
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    OwnerOrigin,
    OwnerState,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.exceptions import MergeConflictsUnresolvedError
from tests.helpers.ownership import (
    OWNERS_FIELD,
    TARGET_OWNERS_FIELD,
    OwnerDataset,
    copies,
    read_owners,
    resolve_owners,
    set_owners,
    site_from,
    site_template,
    template_copies,
)

from ..get_one_node import get_one_diff_node
from ._ownership import (
    OWNER_EDGE_TYPES,
    SET_EDGE_TYPES,
    count_active_holder_edges,
    has_owner_change,
    holder_edges,
    merge,
    merge_without_conflict_check,
    owner_property,
    profile_with_device,
    update_diff,
)
from .conftest import get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase


@dataclass
class OwnerMergeTestCase:
    name: str
    default_branch_owners: tuple[str, ...] | None
    """Group names, written before the branch starts. None is inherit, an empty tuple is "no owner"."""

    branch_owners: tuple[str, ...] | None
    action: DiffAction


OWNER_MERGE_TEST_CASES: list[OwnerMergeTestCase] = [
    OwnerMergeTestCase(
        name="owners_set",
        default_branch_owners=None,
        branch_owners=("dc-emea", "network-emea"),
        action=DiffAction.ADDED,
    ),
    OwnerMergeTestCase(
        name="owner_added",
        default_branch_owners=("dc-emea",),
        branch_owners=("dc-emea", "network-emea"),
        action=DiffAction.UPDATED,
    ),
    OwnerMergeTestCase(
        name="owner_removed",
        default_branch_owners=("dc-emea", "network-emea"),
        branch_owners=("network-emea",),
        action=DiffAction.UPDATED,
    ),
    OwnerMergeTestCase(
        name="no_owner_set",
        default_branch_owners=("dc-emea",),
        branch_owners=(),
        action=DiffAction.UPDATED,
    ),
    OwnerMergeTestCase(
        name="inherit_set",
        default_branch_owners=("dc-emea",),
        branch_owners=None,
        action=DiffAction.REMOVED,
    ),
]
OWNER_SET_MERGE_TEST_CASES = [tc for tc in OWNER_MERGE_TEST_CASES if tc.name not in {"owner_added", "owner_removed"}]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_MERGE_TEST_CASES])
async def test_owner_state_of_a_branch_is_merged(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    test_case: OwnerMergeTestCase,
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    default_branch_owners = dataset.owners(test_case.default_branch_owners)
    branch_owners = dataset.owners(test_case.branch_owners)
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=default_branch_owners)
    branch = await create_branch(db=db, branch_name="owner-merge")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=branch_owners)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == branch_owners
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == default_branch_owners
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(test_case.default_branch_owners),
        dataset.owner_list(test_case.branch_owners),
        test_case.action,
    )

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == branch_owners
    device = await resolve_owners(db=db, branch=default_branch, node_id=dataset.ids["device-a"])
    assert (device.owner_ids, device.origin, device.origin_node_id) == (
        (branch_owners or (), OwnerOrigin.PARENT, tenant_id) if branch_owners is not None else ((), None, None)
    )
    await verify_graph(db=db)


async def test_owner_removed_and_set_again_on_a_branch_stays_after_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    owner_ids = dataset.owners(("dc-emea", "network-emea"))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="owner-set-again")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("network-emea",)))
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=owner_ids)
    await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == owner_ids
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=tenant_id) == len(owner_ids)


@pytest.mark.parametrize(
    "inherited_owners",
    [pytest.param(("dc-emea",), id="owner"), pytest.param((), id="no_owner")],
)
async def test_owner_state_set_again_on_a_branch_does_not_return_after_the_default_branch_replaces_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    inherited_owners: tuple[str, ...],
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    inherited_ids = dataset.owners(inherited_owners)
    default_branch_ids = dataset.owners(("security",))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=inherited_ids)
    branch = await create_branch(db=db, branch_name="owner-set-again")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("network-emea",)))
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=inherited_ids)
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=default_branch_ids)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == inherited_ids
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert not has_owner_change(diff=diff)

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == default_branch_ids
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=tenant_id) == 1
    await verify_graph(db=db)


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
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=tenant_id) == len(merged_owners)


@pytest.mark.parametrize(
    ("branch_owners", "default_branch_owners"),
    [
        pytest.param(("network-emea", "security"), ("dc-emea",), id="one_owner_deleted"),
        pytest.param(("security",), ("network-emea",), id="all_deleted"),
    ],
)
async def test_selected_branch_owners_keep_an_owner_that_the_default_branch_deleted(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    branch_owners: tuple[str, ...],
    default_branch_owners: tuple[str, ...],
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea", "security")))
    branch = await create_branch(db=db, branch_name="deleted-owner")
    # The branch inherits the edge to `security`, so only the write of the selected list can give it to the default branch.
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(branch_owners))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(default_branch_owners))
    security = await NodeManager.get_one(db=db, branch=default_branch, id=dataset.ids["security"], raise_on_error=True)
    await security.delete(db=db)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    conflict = owner_property(diff=diff, node_id=tenant_id).conflict
    assert conflict is not None
    await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH)
    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == dataset.owners(branch_owners)


async def test_node_deleted_on_a_branch_loses_its_owners_at_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    device_id = dataset.ids["device-a"]
    await set_owners(db=db, branch=default_branch, node_id=device_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="node-deleted")
    device = await NodeManager.get_one(db=db, branch=branch, id=device_id, raise_on_error=True)
    await device.delete(db=db)

    assert await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[device_id]) == {}
    assert await read_owners(db=db, branch=default_branch, node_id=device_id) == dataset.owners(("dc-emea",))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert get_one_diff_node(diff_root=diff, node_uuid=device_id).action is DiffAction.REMOVED
    owners = owner_property(diff=diff, node_id=device_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(("dc-emea",)),
        None,
        DiffAction.REMOVED,
    )

    await merge(db=db, branch=branch)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=device_id) is None
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=device_id) == 0


@pytest.mark.parametrize(
    ("holder", "edge_types"),
    [
        pytest.param(NODE_HOLDER, (DatabaseEdgeType.HAS_OWNER.value, DatabaseEdgeType.HAS_NO_OWNER.value), id="owners"),
        pytest.param(NODE_SOURCES_HOLDER, (DatabaseEdgeType.HAS_SOURCE.value,), id="sources"),
    ],
)
async def test_merge_closes_the_owners_that_the_default_branch_gave_to_a_node_that_the_branch_deleted(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: HolderKey,
    edge_types: tuple[str, ...],
) -> None:
    device_id = dataset.ids["device-a"]
    branch = await create_branch(db=db, branch_name="node-deleted")
    # The branch does not read these owners, so its delete does not close them.
    owners_after_branch_start = dataset.owners(("network-emea", "security"))
    await set_owners(
        db=db, branch=default_branch, node_id=device_id, owner_ids=owners_after_branch_start, holder=holder
    )
    device = await NodeManager.get_one(db=db, branch=branch, id=device_id, raise_on_error=True)
    await device.delete(db=db)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    conflict = get_one_diff_node(diff_root=diff, node_uuid=device_id).conflict
    assert conflict is not None
    assert conflict.resolvable is False
    with pytest.raises(MergeConflictsUnresolvedError):
        await merge(db=db, branch=branch)
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=device_id, edge_types=edge_types) == 2

    await merge_without_conflict_check(db=db, branch=branch)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=device_id) is None
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=device_id, edge_types=edge_types) == 0


@pytest.mark.parametrize(
    "holder",
    [
        pytest.param(NODE_HOLDER, id="owners"),
        pytest.param(NODE_SOURCES_HOLDER, id="sources"),
        pytest.param(HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name"), id="attribute"),
    ],
)
@pytest.mark.parametrize(
    ("start", "after"),
    [
        pytest.param(None, ("dc-emea",), id="no_owner_at_the_branch_start"),
        pytest.param(("dc-emea",), ("network-emea", "security"), id="owners_at_the_branch_start"),
    ],
)
@pytest.mark.parametrize(
    "steps",
    [
        pytest.param(("owners", "delete"), id="first_diff"),
        pytest.param(("owners", "diff", "delete"), id="diff_between_the_owners_and_the_delete"),
        pytest.param(("delete", "diff", "owners"), id="diff_between_the_delete_and_the_owners"),
    ],
)
async def test_node_deleted_on_a_branch_conflicts_with_owners_that_the_default_branch_gives_it(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: HolderKey,
    start: tuple[str, ...] | None,
    after: tuple[str, ...],
    steps: tuple[str, ...],
) -> None:
    device_id = dataset.ids["device-a"]
    if start is not None:
        await set_owners(
            db=db, branch=default_branch, node_id=device_id, owner_ids=dataset.owners(start), holder=holder
        )
    branch = await create_branch(db=db, branch_name="node-deleted")
    for step in steps:
        if step == "owners":
            await set_owners(
                db=db, branch=default_branch, node_id=device_id, owner_ids=dataset.owners(after), holder=holder
            )
        elif step == "delete":
            device = await NodeManager.get_one(db=db, branch=branch, id=device_id, raise_on_error=True)
            await device.delete(db=db)
        else:
            await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    conflict = get_one_diff_node(diff_root=diff, node_uuid=device_id).conflict
    assert conflict is not None, list(diff.get_all_conflicts())
    assert (conflict.base_branch_action, conflict.diff_branch_action, conflict.resolvable) == (
        DiffAction.UPDATED,
        DiffAction.REMOVED,
        False,
    )


async def test_car_deleted_on_a_branch_conflicts_with_a_first_color_owner_on_the_default_branch(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, car_accord_main: Node
) -> None:
    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="dc-emea")
    await group.save(db=db)
    branch = await create_branch(db=db, branch_name="car-deleted")
    car = await NodeManager.get_one(db=db, branch=default_branch, id=car_accord_main.id, raise_on_error=True)
    car.color.set_owner(group.id)
    await car.save(db=db)
    branch_car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id, raise_on_error=True)
    await branch_car.delete(db=db)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    conflict = get_one_diff_node(diff_root=diff, node_uuid=car_accord_main.id).conflict
    assert conflict is not None, list(diff.get_all_conflicts())
    assert (conflict.base_branch_action, conflict.diff_branch_action, conflict.resolvable) == (
        DiffAction.UPDATED,
        DiffAction.REMOVED,
        False,
    )


@pytest.mark.parametrize(
    "owner",
    [
        pytest.param("dc-emea", id="branch_agnostic_owner"),
        # A rack stands for an owner of a branch-aware kind, which only the merge deletes on the default branch.
        pytest.param("rack-b", id="branch_aware_owner"),
    ],
)
async def test_owner_deleted_on_a_branch_stays_in_the_owners_after_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset, owner: str
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    owner_ids = dataset.owners((owner, "network-emea"))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=owner_ids)
    branch = await create_branch(db=db, branch_name="owner-deleted")
    node = await NodeManager.get_one(db=db, branch=branch, id=dataset.ids[owner], raise_on_error=True)
    await node.delete(db=db)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id) == owner_ids
    active_on_branch = await OwnershipRepository(db=db, branch=branch, at=None).read_labels(node_ids=list(owner_ids))
    assert set(active_on_branch) == {dataset.ids["network-emea"]}
    active_before_merge = await OwnershipRepository(db=db, branch=default_branch, at=None).read_labels(
        node_ids=list(owner_ids)
    )
    # The delete of a branch-agnostic owner applies to all branches, so only a branch-aware owner waits for the merge.
    assert set(active_before_merge) == (
        {dataset.ids["network-emea"]} if owner == "dc-emea" else {dataset.ids["network-emea"], dataset.ids[owner]}
    )
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert not has_owner_change(diff=diff)

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == owner_ids
    active = await OwnershipRepository(db=db, branch=default_branch, at=None).read_labels(node_ids=list(owner_ids))
    assert set(active) == {dataset.ids["network-emea"]}


async def test_merge_closes_the_owner_edge_of_a_link_to_a_node_that_the_branch_deleted(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    """The owner of one link is one edge, so the link cannot show a deleted owner as a list of owners does."""
    owner_id = dataset.ids["rack-b"]
    # A link that an earlier release stored can have an owner of a branch-aware kind, which only the merge deletes.
    await db.execute_query(
        query="""
    MATCH (:Node {uuid: $device_id})-[:IS_RELATED]-(link:Relationship)-[:IS_RELATED]-(:Node {uuid: $rack_id})
    MATCH (owner:Node {uuid: $owner_id})
    CREATE (link)-[:HAS_OWNER {branch: $branch_name, branch_level: 1, status: "active", from: $at}]->(owner)
        """,
        params={
            "device_id": dataset.ids["device-a"],
            "rack_id": dataset.ids["rack-a"],
            "owner_id": owner_id,
            "branch_name": default_branch.name,
            "at": Timestamp().to_string(),
        },
    )
    branch = await create_branch(db=db, branch_name="link-owner-deleted")
    owner = await NodeManager.get_one(db=db, branch=branch, id=owner_id, raise_on_error=True)
    await owner.delete(db=db)
    await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    query = """
    MATCH (:Relationship)-[r:HAS_OWNER]->(:Node {uuid: $owner_id})
    WHERE r.branch = $branch_name AND r.status = "active" AND r.to IS NULL
    RETURN count(r) AS total
    """
    params = {"owner_id": owner_id, "branch_name": default_branch.name}
    assert (await db.execute_query(query=query, params=params))[0]["total"] == 1

    await merge(db=db, branch=branch)

    assert (await db.execute_query(query=query, params=params))[0]["total"] == 0


async def test_merge_changelog_records_the_owner_change_of_the_changed_node_only(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="owner-changelog")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea", "network-emea")))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    await merge(db=db, branch=branch)

    changelogs = await build_diff_changelog_collector(diff=diff, db=db, branch=default_branch).collect_changelogs()

    assert [(action, changelog.node_id) for action, changelog in changelogs] == [(DiffAction.UPDATED, tenant_id)]
    assert changelogs[0][1].model_dump()["attributes"] == {
        OWNERS_FIELD: {
            "name": OWNERS_FIELD,
            "kind": "List",
            "value": dataset.owner_list(("dc-emea", "network-emea")),
            "value_previous": dataset.owner_list(("dc-emea",)),
            "properties": {},
            "value_update_status": DiffAction.UPDATED,
        }
    }


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_SET_MERGE_TEST_CASES])
async def test_owners_that_a_profile_gives_on_a_branch_are_merged(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    test_case: OwnerMergeTestCase,
) -> None:
    profile_id, device_id = await profile_with_device(db=db, dataset=dataset)
    default_branch_owners = dataset.owners(test_case.default_branch_owners)
    branch_owners = dataset.owners(test_case.branch_owners)
    await set_owners(
        db=db, branch=default_branch, node_id=profile_id, owner_ids=default_branch_owners, holder=NODE_TARGET_HOLDER
    )
    branch = await create_branch(db=db, branch_name="profile-merge")
    await set_owners(db=db, branch=branch, node_id=profile_id, owner_ids=branch_owners, holder=NODE_TARGET_HOLDER)

    on_branch = await resolve_owners(db=db, branch=branch, node_id=device_id)
    on_default_branch = await resolve_owners(db=db, branch=default_branch, node_id=device_id)
    assert (on_branch.owner_ids, on_branch.origin) == (
        (branch_owners, OwnerOrigin.PROFILE) if branch_owners is not None else ((), None)
    )
    assert (on_default_branch.owner_ids, on_default_branch.origin) == (
        (default_branch_owners, OwnerOrigin.PROFILE) if default_branch_owners is not None else ((), None)
    )
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert [node.uuid for node in diff.nodes] == [profile_id]
    owners = owner_property(diff=diff, node_id=profile_id, field_name=TARGET_OWNERS_FIELD)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(test_case.default_branch_owners),
        dataset.owner_list(test_case.branch_owners),
        test_case.action,
    )

    await merge(db=db, branch=branch)

    assert (
        await read_owners(db=db, branch=default_branch, node_id=profile_id, holder=NODE_TARGET_HOLDER) == branch_owners
    )
    merged = await resolve_owners(db=db, branch=default_branch, node_id=device_id)
    assert (merged.owner_ids, merged.origin, merged.origin_node_id) == (
        (branch_owners, OwnerOrigin.PROFILE, profile_id) if branch_owners is not None else ((), None, None)
    )
    await verify_graph(db=db)


async def test_template_changed_on_a_branch_gives_its_new_owners_to_the_nodes_created_after_the_change(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    template = await Node.init(db=db, schema="TemplateTestSite")
    await template.new(db=db, template_name="emea-site")
    await template.save(db=db)
    first_owners, second_owners = dataset.owners(("dc-emea",)), dataset.owners(("security",))
    await set_owners(
        db=db, branch=default_branch, node_id=template.id, owner_ids=first_owners, holder=NODE_TARGET_HOLDER
    )
    first_site = await create_node(
        data={"name": "site-before", "object_template": {"id": template.id}},
        db=db,
        branch=default_branch,
        schema=registry.schema.get_node_schema(name="TestSite", branch=default_branch),
    )
    branch = await create_branch(db=db, branch_name="template-merge")
    await set_owners(db=db, branch=branch, node_id=template.id, owner_ids=second_owners, holder=NODE_TARGET_HOLDER)
    second_site = await create_node(
        data={"name": "site-after", "object_template": {"id": template.id}},
        db=db,
        branch=branch,
        schema=registry.schema.get_node_schema(name="TestSite", branch=branch),
    )

    on_branch = await resolve_owners(db=db, branch=branch, node_id=second_site.id)
    assert (on_branch.owner_ids, on_branch.origin, on_branch.origin_node_id) == (
        second_owners,
        OwnerOrigin.TEMPLATE,
        template.id,
    )
    assert await read_owners(db=db, branch=default_branch, node_id=template.id, holder=NODE_TARGET_HOLDER) == (
        first_owners
    )
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    changes = {
        (node.uuid, attribute.name): attribute.get_property(property_type=DatabaseEdgeType.HAS_OWNER)
        for node in diff.nodes
        for attribute in node.attributes
        if attribute.name in (OWNERS_FIELD, TARGET_OWNERS_FIELD)
    }
    assert {key: (change.previous_value, change.new_value, change.action) for key, change in changes.items()} == {
        (template.id, TARGET_OWNERS_FIELD): (
            dataset.owner_list(("dc-emea",)),
            dataset.owner_list(("security",)),
            DiffAction.UPDATED,
        ),
        (second_site.id, OWNERS_FIELD): (None, dataset.owner_list(("security",)), DiffAction.ADDED),
    }

    await merge(db=db, branch=branch)

    resolved = {
        site.id: await resolve_owners(db=db, branch=default_branch, node_id=site.id)
        for site in (first_site, second_site)
    }
    assert {
        site_id: (owners.state, owners.owner_ids, owners.origin, owners.origin_node_id)
        for site_id, owners in resolved.items()
    } == {
        first_site.id: (OwnerState.INHERIT, first_owners, OwnerOrigin.TEMPLATE, template.id),
        second_site.id: (OwnerState.INHERIT, second_owners, OwnerOrigin.TEMPLATE, template.id),
    }
    await verify_graph(db=db)


async def test_template_deleted_on_a_branch_leaves_its_copies_as_own_owners_after_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    owner_ids = dataset.owners(("dc-emea",))
    template = await site_template(db=db, default_branch=default_branch, dataset=dataset)
    site_id = await site_from(db=db, branch=default_branch, template=template, name="site-before")
    branch = await create_branch(db=db, branch_name="template-deleted")
    # The branch does not read this site, so its delete does not close the marks of the site.
    later_site_id = await site_from(db=db, branch=default_branch, template=template, name="site-after")
    branch_template = await NodeManager.get_one(db=db, branch=branch, id=template.id, raise_on_error=True)

    await branch_template.delete(db=db)

    assert await template_copies(db=db, branch=branch, node_id=site_id) == copies(owner_ids, None)
    for node_id in (site_id, later_site_id):
        assert await template_copies(db=db, branch=default_branch, node_id=node_id) == copies(owner_ids, template.id)
    await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()

    await merger.merge_graph(at=merge_at)

    for node_id in (site_id, later_site_id):
        assert await template_copies(db=db, branch=default_branch, node_id=node_id) == copies(owner_ids, None)
    assert await template_copies(db=db, branch=branch, node_id=site_id) == copies(owner_ids, None)
    resolved = await resolve_owners(db=db, branch=default_branch, node_id=site_id)
    assert (resolved.state, resolved.owner_ids, resolved.origin, resolved.origin_node_id) == (
        OwnerState.OWNERS,
        owner_ids,
        OwnerOrigin.SELF,
        site_id,
    )
    await verify_graph(db=db)

    await merger.rollback(merge_started_at=merge_at)

    for node_id in (site_id, later_site_id):
        assert await template_copies(db=db, branch=default_branch, node_id=node_id) == copies(owner_ids, template.id)


@pytest.mark.parametrize(
    "deletes_template",
    [pytest.param(False, id="same_owners_written"), pytest.param(True, id="template_deleted")],
)
async def test_branch_that_only_closes_the_template_mark_shows_the_owners_in_the_diff(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    deletes_template: bool,
) -> None:
    owner_ids = dataset.owners(("dc-emea",))
    template = await site_template(db=db, default_branch=default_branch, dataset=dataset)
    site_id = await site_from(db=db, branch=default_branch, template=template, name="site-a")
    branch = await create_branch(db=db, branch_name="mark-closed")
    if deletes_template:
        branch_template = await NodeManager.get_one(db=db, branch=branch, id=template.id, raise_on_error=True)
        await branch_template.delete(db=db)
    else:
        await set_owners(db=db, branch=branch, node_id=site_id, owner_ids=owner_ids)
    assert (await template_copies(db=db, branch=branch, node_id=site_id))[HolderKind.NODE] == (owner_ids, None)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    owners = owner_property(diff=diff, node_id=site_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(("dc-emea",)),
        dataset.owner_list(("dc-emea",)),
        DiffAction.UPDATED,
    )
    assert diff.get_all_conflicts() == {}

    await merge(db=db, branch=branch)

    assert (await template_copies(db=db, branch=default_branch, node_id=site_id))[HolderKind.NODE] == (owner_ids, None)


@pytest.mark.parametrize("mark_closed_on_branch", [pytest.param(True, id="branch"), pytest.param(False, id="default")])
async def test_closed_template_mark_on_one_branch_does_not_conflict_with_new_owners_on_the_other(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    mark_closed_on_branch: bool,
) -> None:
    new_owner_ids = dataset.owners(("security",))
    template = await site_template(db=db, default_branch=default_branch, dataset=dataset)
    site_id = await site_from(db=db, branch=default_branch, template=template, name="site-a")
    branch = await create_branch(db=db, branch_name="mark-closed")
    closes_mark, changes_owners = (branch, default_branch) if mark_closed_on_branch else (default_branch, branch)
    await set_owners(db=db, branch=closes_mark, node_id=site_id, owner_ids=dataset.owners(("dc-emea",)))
    await set_owners(db=db, branch=changes_owners, node_id=site_id, owner_ids=new_owner_ids)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    assert diff.get_all_conflicts() == {}

    await merge(db=db, branch=branch)

    assert (await template_copies(db=db, branch=default_branch, node_id=site_id))[HolderKind.NODE] == (
        new_owner_ids,
        None,
    )


async def test_merge_closes_the_owners_that_the_default_branch_gave_through_a_profile_that_the_branch_deleted(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    profile_id, device_id = await profile_with_device(db=db, dataset=dataset)
    await set_owners(
        db=db, branch=default_branch, node_id=dataset.ids["tenant-a"], owner_ids=dataset.owners(("network-emea",))
    )
    branch = await create_branch(db=db, branch_name="profile-deleted")
    # The branch does not read these owners, so its delete does not close them.
    await set_owners(
        db=db,
        branch=default_branch,
        node_id=profile_id,
        owner_ids=dataset.owners(("dc-emea", "security")),
        holder=NODE_TARGET_HOLDER,
    )
    profile = await NodeManager.get_one(db=db, branch=branch, id=profile_id, raise_on_error=True)
    await profile.delete(db=db)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    conflict = get_one_diff_node(diff_root=diff, node_uuid=profile_id).conflict
    assert conflict is not None
    assert conflict.resolvable is False
    with pytest.raises(MergeConflictsUnresolvedError):
        await merge(db=db, branch=branch)
    assert (
        await count_active_holder_edges(
            db=db, branch=default_branch, node_id=profile_id, edge_types=(*OWNER_EDGE_TYPES, *SET_EDGE_TYPES)
        )
        == 3
    )

    await merge_without_conflict_check(db=db, branch=branch)

    assert (
        await count_active_holder_edges(
            db=db, branch=default_branch, node_id=profile_id, edge_types=(*OWNER_EDGE_TYPES, *SET_EDGE_TYPES)
        )
        == 0
    )
    merged = await resolve_owners(db=db, branch=default_branch, node_id=device_id)
    assert (merged.owner_ids, merged.origin, merged.origin_node_id) == (
        dataset.owners(("network-emea",)),
        OwnerOrigin.PARENT,
        dataset.ids["tenant-a"],
    )


NAME_HOLDER = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name")


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_SET_MERGE_TEST_CASES])
async def test_owner_state_of_an_attribute_on_a_branch_is_merged(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    test_case: OwnerMergeTestCase,
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    default_branch_owners = dataset.owners(test_case.default_branch_owners)
    branch_owners = dataset.owners(test_case.branch_owners)
    await set_owners(
        db=db, branch=default_branch, node_id=tenant_id, owner_ids=default_branch_owners, holder=NAME_HOLDER
    )
    branch = await create_branch(db=db, branch_name="owner-merge")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=branch_owners, holder=NAME_HOLDER)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id, holder=NAME_HOLDER) == branch_owners
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id, field_name="name")
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(test_case.default_branch_owners),
        dataset.owner_list(test_case.branch_owners),
        test_case.action,
    )

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id, holder=NAME_HOLDER) == branch_owners
    await verify_graph(db=db)


async def test_owner_of_an_attribute_replaced_through_the_owner_property_on_a_branch_is_merged(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    tenant = await NodeManager.get_one(db=db, branch=default_branch, id=tenant_id, raise_on_error=True)
    tenant.get_attribute(name="name").owner = dataset.ids["dc-emea"]
    await tenant.save(db=db)
    branch = await create_branch(db=db, branch_name="owner-merge")
    tenant = await NodeManager.get_one(db=db, branch=branch, id=tenant_id, raise_on_error=True)
    name = tenant.get_attribute(name="name")
    name.value = "tenant-renamed"
    name.owner = dataset.ids["security"]
    await tenant.save(db=db)

    assert await read_owners(db=db, branch=branch, node_id=tenant_id, holder=NAME_HOLDER) == (dataset.ids["security"],)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id, field_name="name")
    assert (owners.previous_value, owners.new_value, owners.action, owners.previous_label, owners.new_label) == (
        dataset.owner_list(("dc-emea",)),
        dataset.owner_list(("security",)),
        DiffAction.UPDATED,
        "dc-emea",
        "security",
    )
    name_diff = get_one_diff_node(diff_root=diff, node_uuid=tenant_id).get_attribute(name="name")
    assert {prop.property_type for prop in name_diff.properties} == {
        DatabaseEdgeType.HAS_VALUE,
        DatabaseEdgeType.HAS_OWNER,
    }

    await merge(db=db, branch=branch)

    merged = await NodeManager.get_one(db=db, branch=default_branch, id=tenant_id, raise_on_error=True)
    assert merged.get_attribute(name="name").value == "tenant-renamed"
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id, holder=NAME_HOLDER) == (
        dataset.ids["security"],
    )
    await verify_graph(db=db)


async def _count_field_owner_sets(db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[int, int]:
    """Count the sets of owners of the fields of a node, and the open owner edges of these sets on one branch."""
    query = """
    MATCH (n:Node {uuid: $node_id})-[:HAS_OWNER_SET]->(s:OwnerSet)
    OPTIONAL MATCH (s)-[r:HAS_OWNER|HAS_NO_OWNER]->()
    WHERE r.branch = $branch_name AND r.status = "active" AND r.to IS NULL
    RETURN count(DISTINCT s) AS sets, count(DISTINCT r) AS edges
    """
    results = await db.execute_query(query=query, params={"node_id": node_id, "branch_name": branch.name})
    return results[0]["sets"], results[0]["edges"]


@pytest.mark.parametrize(
    ("second_branch_owners", "selection", "merged_owners"),
    [
        pytest.param(("dc-emea",), None, ("dc-emea",), id="same_owners"),
        pytest.param(("security",), ConflictSelection.DIFF_BRANCH, ("security",), id="second_branch_selected"),
        pytest.param(("security",), ConflictSelection.BASE_BRANCH, ("dc-emea",), id="default_branch_selected"),
    ],
)
async def test_two_branches_that_each_set_the_first_owners_of_a_relationship_leave_one_owner_state(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    second_branch_owners: tuple[str, ...],
    selection: ConflictSelection | None,
    merged_owners: tuple[str, ...],
) -> None:
    device_id = dataset.ids["device-a"]
    field_name = "rack__owners"
    rack_holder = field_holder(
        schema=registry.schema.get(name="TestDevice", branch=default_branch, duplicate=False), field_name="rack"
    )
    assert rack_holder is not None
    first_branch = await create_branch(db=db, branch_name="first-owners-a")
    second_branch = await create_branch(db=db, branch_name="first-owners-b")
    await set_owners(
        db=db, branch=first_branch, node_id=device_id, owner_ids=dataset.owners(("dc-emea",)), holder=rack_holder
    )
    await set_owners(
        db=db,
        branch=second_branch,
        node_id=device_id,
        owner_ids=dataset.owners(second_branch_owners),
        holder=rack_holder,
    )

    diff = await update_diff(db=db, default_branch=default_branch, branch=first_branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=device_id, field_name=field_name)
    assert (owners.previous_value, owners.new_value, owners.action, owners.new_label) == (
        None,
        dataset.owner_list(("dc-emea",)),
        DiffAction.ADDED,
        "dc-emea",
    )
    await merge(db=db, branch=first_branch)
    assert await read_owners(db=db, branch=default_branch, node_id=device_id, holder=rack_holder) == dataset.owners(
        ("dc-emea",)
    )

    diff = await update_diff(
        db=db, default_branch=default_branch, branch=second_branch, diff_repository=diff_repository
    )
    conflict = owner_property(diff=diff, node_id=device_id, field_name=field_name).conflict
    if selection is None:
        assert conflict is None
    else:
        assert list(diff.get_all_conflicts()) == [f"data/{device_id}/{field_name}/property/HAS_OWNER"]
        assert conflict is not None
        assert (conflict.base_branch_value, conflict.diff_branch_value) == (
            dataset.owner_list(("dc-emea",)),
            dataset.owner_list(second_branch_owners),
        )
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)
    await merge(db=db, branch=second_branch)

    assert await read_owners(db=db, branch=default_branch, node_id=device_id, holder=rack_holder) == dataset.owners(
        merged_owners
    )
    assert await _count_field_owner_sets(db=db, branch=default_branch, node_id=device_id) == (1, 1)
    await verify_graph(db=db)


MIXED_SUPPORT_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="AwareThing",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="serial", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
            ],
        ),
        NodeSchema(
            name="SharedThing",
            namespace="Test",
            branch=BranchSupportType.AGNOSTIC,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True, branch=BranchSupportType.AGNOSTIC),
                AttributeSchema(name="note", kind="Text", optional=True, branch=BranchSupportType.AWARE),
            ],
        ),
    ]
)


async def _create_mixed_support_node(db: InfrahubDatabase, default_branch: Branch, kind: str) -> str:
    registry.schema.register_schema(schema=MIXED_SUPPORT_SCHEMA, branch=default_branch.name)
    node = await Node.init(db=db, schema=kind, branch=default_branch)
    await node.new(db=db, name="thing-a")
    await node.save(db=db)
    return node.get_id()


async def test_owners_of_a_branch_agnostic_attribute_written_on_a_branch_apply_to_all_branches(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    node_id = await _create_mixed_support_node(db=db, default_branch=default_branch, kind="TestAwareThing")
    holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="serial")
    owner_ids = dataset.owners(("dc-emea",))
    branch = await create_branch(db=db, branch_name="agnostic-attribute")

    await set_owners(db=db, branch=branch, node_id=node_id, owner_ids=owner_ids, holder=holder)

    assert await read_owners(db=db, branch=default_branch, node_id=node_id, holder=holder) == owner_ids
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert not [node for node in diff.nodes if node.uuid == node_id]
    await merge(db=db, branch=branch)
    assert await read_owners(db=db, branch=default_branch, node_id=node_id, holder=holder) == owner_ids
    await verify_graph(db=db)


async def test_owners_of_a_branch_aware_attribute_of_a_branch_agnostic_node_are_merged(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    node_id = await _create_mixed_support_node(db=db, default_branch=default_branch, kind="TestSharedThing")
    holder = HolderKey(kind=HolderKind.ATTRIBUTE, attribute="note")
    owner_ids = dataset.owners(("dc-emea", "security"))
    branch = await create_branch(db=db, branch_name="aware-attribute")

    await set_owners(db=db, branch=branch, node_id=node_id, owner_ids=owner_ids, holder=holder)

    assert await read_owners(db=db, branch=branch, node_id=node_id, holder=holder) == owner_ids
    assert await read_owners(db=db, branch=default_branch, node_id=node_id, holder=holder) is None
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=node_id, field_name="note")
    assert (owners.previous_value, owners.new_value, owners.action) == (
        None,
        dataset.owner_list(("dc-emea", "security")),
        DiffAction.ADDED,
    )
    await merge(db=db, branch=branch)
    assert await read_owners(db=db, branch=default_branch, node_id=node_id, holder=holder) == owner_ids
    await verify_graph(db=db)


async def test_owner_write_on_a_branch_writes_the_owners_of_a_branch_agnostic_node_on_the_global_branch(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    group_id = dataset.ids["security"]
    await set_owners(db=db, branch=default_branch, node_id=group_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="global-owner-merge")
    await set_owners(db=db, branch=branch, node_id=group_id, owner_ids=dataset.owners(("network-emea",)))
    await set_owners(db=db, branch=branch, node_id=dataset.ids["tenant-a"], owner_ids=dataset.owners(("dc-emea",)))
    edges = await holder_edges(db=db, node_id=group_id)
    assert {(edge[5], edge[1]) for edge in edges} == {(GLOBAL_BRANCH_NAME, "active"), (GLOBAL_BRANCH_NAME, "deleted")}
    assert await read_owners(db=db, branch=default_branch, node_id=group_id) == dataset.owners(("network-emea",))

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    assert [node.uuid for node in diff.nodes if node.uuid == group_id] == []
    await merge(db=db, branch=branch)

    assert await holder_edges(db=db, node_id=group_id) == edges
    for read_branch in (default_branch, branch):
        assert await read_owners(db=db, branch=read_branch, node_id=group_id) == dataset.owners(("network-emea",))
    await verify_graph(db=db)


async def _select_the_branch_owners_of_an_attribute_conflict(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    branch_name: str,
) -> tuple[str, Branch, str]:
    """Give other owners to the attribute `name` of `tenant-a` on both branches and select the branch in the conflict.

    Return the ID of the tenant, the branch and the ID of the conflict.
    """
    tenant_id = dataset.ids["tenant-a"]
    await set_owners(
        db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)), holder=NAME_HOLDER
    )
    branch = await create_branch(db=db, branch_name=branch_name)
    await set_owners(
        db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("network-emea",)), holder=NAME_HOLDER
    )
    await set_owners(
        db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("security",)), holder=NAME_HOLDER
    )
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    conflict = owner_property(diff=diff, node_id=tenant_id, field_name="name").conflict
    assert conflict is not None
    await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=ConflictSelection.DIFF_BRANCH)
    return tenant_id, branch, conflict.uuid


async def test_stored_conflict_with_one_owner_id_as_value_gives_that_owner_at_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id, branch, conflict_id = await _select_the_branch_owners_of_an_attribute_conflict(
        db=db,
        default_branch=default_branch,
        diff_repository=diff_repository,
        dataset=dataset,
        branch_name="stored-conflict",
    )
    # A diff of a release that kept one owner for each attribute stores the owner ID and not a list.
    await db.execute_query(
        query="MATCH (c:DiffConflict {uuid: $uuid}) SET c.diff_branch_value = $owner_id",
        params={"uuid": conflict_id, "owner_id": dataset.ids["security"]},
    )

    await merge(db=db, branch=branch)

    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id, holder=NAME_HOLDER) == (
        dataset.ids["security"],
    )


async def test_rollback_of_a_merge_that_wrote_the_owners_of_an_attribute_restores_the_audit_metadata(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id, branch, _ = await _select_the_branch_owners_of_an_attribute_conflict(
        db=db,
        default_branch=default_branch,
        diff_repository=diff_repository,
        dataset=dataset,
        branch_name="owner-rollback",
    )
    metadata_query = """
    MATCH (n:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: "name"})
    RETURN [n.updated_at, n.updated_by, a.updated_at, a.updated_by] AS metadata
    """
    before = (await db.execute_query(query=metadata_query, params={"node_id": tenant_id}))[0]["metadata"]
    assert None not in before
    merger = await get_diff_merger(db=db, branch=branch)
    merge_at = Timestamp()
    await merger.merge_graph(at=merge_at)
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id, holder=NAME_HOLDER) == dataset.owners(
        ("security",)
    )
    merged = (await db.execute_query(query=metadata_query, params={"node_id": tenant_id}))[0]["metadata"]
    assert merged != before

    await merger.rollback(merge_started_at=merge_at)

    after = (await db.execute_query(query=metadata_query, params={"node_id": tenant_id}))[0]["metadata"]
    assert after == before
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id, holder=NAME_HOLDER) == dataset.owners(
        ("network-emea",)
    )


async def test_owner_diff_of_more_nodes_than_the_query_size_limit_reads_the_nodes_in_batches(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_ids = [dataset.ids[name] for name in ("tenant-a", "rack-a", "rack-b", "device-a")]
    branch = await create_branch(db=db, branch_name="owner-batches")
    for node_id in node_ids:
        await set_owners(db=db, branch=branch, node_id=node_id, owner_ids=dataset.owners(("dc-emea",)))
        await set_owners(db=db, branch=default_branch, node_id=node_id, owner_ids=dataset.owners(("security",)))
    branch_from_time = Timestamp(branch.get_branched_from())
    request = OwnerDiffRequest(
        base_branch=default_branch,
        diff_branch=branch,
        branch_from_time=branch_from_time,
        from_time=branch_from_time,
        to_time=Timestamp(),
        include_unchanged=False,
        previous_node_specifiers=None,
        node_kinds=None,
        node_uuids=None,
    )
    batches: list[list[str] | None] = []
    execute = DiffOwnerHoldersQuery.execute

    async def recording_execute(
        self: DiffOwnerHoldersQuery, db: InfrahubDatabase, timeout_seconds: float | None = None
    ) -> DiffOwnerHoldersQuery:
        batches.append(self.node_uuids)
        return await execute(self, db=db, timeout_seconds=timeout_seconds)

    monkeypatch.setattr(DiffOwnerHoldersQuery, "execute", recording_execute)

    async def owner_diff(query_size_limit: int) -> list[list[DiffNode]]:
        monkeypatch.setattr(config.SETTINGS.database, "query_size_limit", query_size_limit)
        roots = [
            DiffRoot(from_time=request.from_time, to_time=request.to_time, uuid=name, branch=name)
            for name in (branch.name, default_branch.name)
        ]
        differ = OwnershipDiffer(db=db)
        await differ.add_owner_changes(
            request=request,
            branch_root=roots[0],
            base_root=roots[1],
            branch_changes=await differ.get_branch_changes(request=request),
        )
        return [sorted(root.nodes, key=lambda node: node.uuid) for root in roots]

    expected = await owner_diff(query_size_limit=len(node_ids))
    batches.clear()

    assert await owner_diff(query_size_limit=2) == expected
    assert all(len(diff_nodes) == len(node_ids) for diff_nodes in expected)
    node_batches = [batch for batch in batches if batch is not None]
    assert len(node_batches) > 1
    assert all(len(batch) <= 2 for batch in node_batches)


async def owner_diff_values(
    db: InfrahubDatabase,
    base_branch: Branch,
    diff_branch: Branch,
    branch_from_time: Timestamp,
    from_time: Timestamp,
    to_time: Timestamp,
    previous_node_specifiers: NodeFieldSpecifierMap | None = None,
) -> tuple[list[tuple[str | None, str | None]], list[tuple[str | None, str | None]]]:
    """Return the node owner changes of the diff branch and of the base branch in one time range."""
    request = OwnerDiffRequest(
        base_branch=base_branch,
        diff_branch=diff_branch,
        branch_from_time=branch_from_time,
        from_time=from_time,
        to_time=to_time,
        include_unchanged=False,
        previous_node_specifiers=previous_node_specifiers,
        node_kinds=None,
        node_uuids=None,
    )
    branch_root = DiffRoot(from_time=from_time, to_time=to_time, uuid=diff_branch.name, branch=diff_branch.name)
    base_root = DiffRoot(from_time=from_time, to_time=to_time, uuid=base_branch.name, branch=base_branch.name)
    differ = OwnershipDiffer(db=db)
    await differ.add_owner_changes(
        request=request,
        branch_root=branch_root,
        base_root=base_root,
        branch_changes=await differ.get_branch_changes(request=request),
    )
    branch_values, base_values = (
        [
            (prop.previous_value, prop.new_value)
            for node in root.nodes
            for attribute in node.attributes
            if attribute.name == OWNERS_FIELD
            for prop in attribute.properties
        ]
        for root in (branch_root, base_root)
    )
    return branch_values, base_values


async def test_owner_write_at_the_end_of_a_diff_time_range_is_in_the_next_time_range(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    branch = await create_branch(db=db, branch_name="owner-range-end")
    branch_from_time = Timestamp(branch.get_branched_from())
    range_end = Timestamp()
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)), at=range_end)

    first_range = await owner_diff_values(db, default_branch, branch, branch_from_time, branch_from_time, range_end)
    second_range = await owner_diff_values(db, default_branch, branch, branch_from_time, range_end, Timestamp())

    assert first_range == ([], [])
    assert second_range == ([(None, dataset.owner_list(("dc-emea",)))], [])


async def test_default_branch_owner_write_at_the_end_of_a_diff_time_range_is_in_the_next_time_range(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    branch = await create_branch(db=db, branch_name="base-owner-range-end")
    branch_from_time = Timestamp(branch.get_branched_from())
    previous_fields = NodeFieldSpecifierMap()
    previous_fields.add_entry(node_uuid=tenant_id, kind="TestTenant", field_name=OWNERS_FIELD)
    range_end = Timestamp()
    await set_owners(
        db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)), at=range_end
    )

    second_range = await owner_diff_values(
        db, default_branch, branch, branch_from_time, range_end, Timestamp(), previous_node_specifiers=previous_fields
    )

    assert second_range == ([], [(None, dataset.owner_list(("dc-emea",)))])


async def test_owner_write_at_the_start_of_a_default_branch_diff_is_in_the_diff(
    db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    range_start = Timestamp()
    await set_owners(
        db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)), at=range_start
    )

    branch_values, _ = await owner_diff_values(
        db, default_branch, default_branch, range_start, range_start, Timestamp()
    )

    assert branch_values == [(None, dataset.owner_list(("dc-emea",)))]

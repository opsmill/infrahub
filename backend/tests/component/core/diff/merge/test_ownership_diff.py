from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import DiffAction, InfrahubKind, PathType
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.conflicts_extractor import DiffConflictsExtractor
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m085_close_repository_owner_edges import Migration085
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.ownership.models import NODE_HOLDER, NODE_SOURCES_HOLDER, HolderKey, OwnerOrigin
from tests.helpers.ownership import (
    ADD_ATTRIBUTE_OWNER,
    ADD_NAME_OWNER,
    OWNERS_FIELD,
    SOURCES_FIELD,
    OwnerDataset,
    add_owner_edge,
    create_groups,
    resolve_owners,
    set_owners,
)

from ._ownership import owner_property, update_diff

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase


async def test_owner_change_lists_one_node_with_the_labels_of_its_owners(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    before, after = ("dc-emea", "network-emea"), ("network-emea", "security")
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(before))
    branch = await create_branch(db=db, branch_name="owner-change")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(after))

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    assert [(node.uuid, node.action) for node in diff.nodes] == [(tenant_id, DiffAction.UPDATED)]
    assert [(attribute.name, attribute.action) for attribute in next(iter(diff.nodes)).attributes] == [
        (OWNERS_FIELD, DiffAction.UPDATED)
    ]
    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(before),
        dataset.owner_list(after),
        DiffAction.UPDATED,
    )
    assert (owners.previous_label, owners.new_label) == (dataset.owner_labels(before), dataset.owner_labels(after))
    assert diff.get_all_conflicts() == {}
    # The rack and the device inherit, so each one reads the owners of the tenant without a change of its own.
    for name in ("rack-a", "device-a"):
        on_branch = await resolve_owners(db=db, branch=branch, node_id=dataset.ids[name])
        assert (on_branch.owner_ids, on_branch.origin, on_branch.origin_node_id) == (
            dataset.owners(after),
            OwnerOrigin.PARENT,
            tenant_id,
        )
        on_default_branch = await resolve_owners(db=db, branch=default_branch, node_id=dataset.ids[name])
        assert on_default_branch.owner_ids == dataset.owners(before)


@pytest.mark.parametrize(
    ("holder", "field_name", "property_type", "mark"),
    [
        pytest.param(NODE_HOLDER, OWNERS_FIELD, DatabaseEdgeType.HAS_OWNER, "deleted owner", id="owners"),
        pytest.param(NODE_SOURCES_HOLDER, SOURCES_FIELD, DatabaseEdgeType.HAS_SOURCE, "deleted source", id="sources"),
    ],
)
async def test_deleted_owner_or_source_has_a_mark_in_the_labels(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: HolderKey,
    field_name: str,
    property_type: DatabaseEdgeType,
    mark: str,
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    before, after = ("dc-emea", "security"), ("dc-emea", "network-emea", "security")
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(before), holder=holder)
    branch = await create_branch(db=db, branch_name="owner-deleted")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(after), holder=holder)
    # An account group is branch-agnostic, so the delete applies to the two branches.
    group = await NodeManager.get_one(db=db, branch=branch, id=dataset.ids["security"], raise_on_error=True)
    await group.delete(db=db)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    owners = owner_property(diff=diff, node_id=tenant_id, field_name=field_name, property_type=property_type)
    assert (owners.previous_value, owners.new_value) == (dataset.owner_list(before), dataset.owner_list(after))
    assert (owners.previous_label, owners.new_label) == (
        dataset.owner_labels(before, deleted=("security",), mark=mark),
        dataset.owner_labels(after, deleted=("security",), mark=mark),
    )


async def test_later_diff_update_keeps_the_whole_owner_lists(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    first, second, third = ("dc-emea",), ("dc-emea", "network-emea"), ("network-emea", "security")
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(first))
    branch = await create_branch(db=db, branch_name="owner-updates")
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(second))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value) == (dataset.owner_list(first), dataset.owner_list(second))

    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(third))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value, owners.action) == (
        dataset.owner_list(first),
        dataset.owner_list(third),
        DiffAction.UPDATED,
    )
    assert owners.new_label == dataset.owner_labels(third)
    assert owners.conflict is None

    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("security",)))
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    owners = owner_property(diff=diff, node_id=tenant_id)
    assert owners.conflict is not None
    assert (owners.conflict.base_branch_value, owners.conflict.diff_branch_value) == (
        dataset.owner_list(("security",)),
        dataset.owner_list(third),
    )


@dataclass
class OwnerConflictTestCase:
    name: str
    default_branch_owners: tuple[str, ...] | None
    """Group names, written on the default branch after the branch starts. None is inherit."""

    branch_owners: tuple[str, ...] | None


OWNER_CONFLICT_TEST_CASES: list[OwnerConflictTestCase] = [
    OwnerConflictTestCase(
        name="different_owners_replace_the_same_owner",
        default_branch_owners=("network-emea",),
        branch_owners=("security",),
    ),
    OwnerConflictTestCase(
        name="no_owner_against_inherit",
        default_branch_owners=(),
        branch_owners=None,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_CONFLICT_TEST_CASES])
async def test_owner_changes_on_both_branches_conflict_when_the_lists_differ(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    test_case: OwnerConflictTestCase,
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=dataset.owners(("dc-emea",)))
    branch = await create_branch(db=db, branch_name="owner-conflict")
    default_branch_owners = dataset.owners(test_case.default_branch_owners)
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=default_branch_owners)
    await set_owners(db=db, branch=branch, node_id=tenant_id, owner_ids=dataset.owners(test_case.branch_owners))

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    owners = owner_property(diff=diff, node_id=tenant_id)
    assert (owners.previous_value, owners.new_value) == (
        dataset.owner_list(("dc-emea",)),
        dataset.owner_list(test_case.branch_owners),
    )
    data_conflicts = await DiffConflictsExtractor(db=db).get_data_conflicts(enriched_diff_root=diff)
    assert owners.conflict is not None
    assert (owners.conflict.base_branch_value, owners.conflict.diff_branch_value) == (
        dataset.owner_list(test_case.default_branch_owners),
        dataset.owner_list(test_case.branch_owners),
    )
    assert (owners.conflict.base_branch_label, owners.conflict.diff_branch_label) == (
        dataset.owner_labels(test_case.default_branch_owners) if test_case.default_branch_owners else None,
        dataset.owner_labels(test_case.branch_owners) if test_case.branch_owners else None,
    )
    assert [
        (conflict.id, conflict.name, conflict.path, conflict.path_type, conflict.property_name)
        for conflict in data_conflicts
    ] == [
        (
            tenant_id,
            OWNERS_FIELD,
            f"data/{tenant_id}/{OWNERS_FIELD}/property/HAS_OWNER",
            PathType.ATTRIBUTE,
            "HAS_OWNER",
        )
    ]
    assert [(change.branch, change.previous, change.new) for change in data_conflicts[0].changes] == [
        (default_branch.name, dataset.owner_list(("dc-emea",)), dataset.owner_list(test_case.default_branch_owners)),
        (branch.name, dataset.owner_list(("dc-emea",)), dataset.owner_list(test_case.branch_owners)),
    ]


@pytest.mark.parametrize("owner_branch", ["default_branch", "global_branch"])
async def test_repository_owner_that_the_upgrade_closes_gives_no_change_in_the_diff_of_an_older_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    car_accord_main: Node,
    owner_branch: str,
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    if owner_branch == "default_branch":
        await add_owner_edge(
            db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car_accord_main.id, owner_id=repository.id
        )
    else:
        group_id = (await create_groups(db=db, names=("network-team",)))["network-team"]
        await add_owner_edge(
            db=db, query=ADD_NAME_OWNER, branch=registry.get_global_branch(), node_id=group_id, owner_id=repository.id
        )
    branch = await create_branch(db=db, branch_name="before-upgrade")
    result = await Migration085().execute(migration_input=MigrationInput(db=db))
    assert result.errors == []

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    assert [(node.kind, node.action) for node in diff.nodes] == []


async def test_repository_owner_that_the_upgrade_closes_gives_no_conflict_with_a_delete_on_an_older_branch(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, car_accord_main: Node
) -> None:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="repo01", location="git@github.com:user/repo01.git")
    await repository.save(db=db)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car_accord_main.id, owner_id=repository.id
    )
    branch = await create_branch(db=db, branch_name="before-upgrade")
    result = await Migration085().execute(migration_input=MigrationInput(db=db))
    assert result.errors == []
    car = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id, raise_on_error=True)
    await car.delete(db=db)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)

    assert diff.get_all_conflicts() == {}

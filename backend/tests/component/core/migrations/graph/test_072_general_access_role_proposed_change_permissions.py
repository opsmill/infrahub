from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.initialization import first_time_initialization
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m072_general_access_role_proposed_change_permissions import (
    GENERAL_ACCESS_ROLE_NAME,
    PROPOSED_CHANGE_PERMISSIONS,
    Migration072,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def _get_general_access_proposed_change_permissions(
    db: InfrahubDatabase,
) -> tuple[Node, list[Node]]:
    roles = await NodeManager.query(
        db=db, schema=InfrahubKind.ACCOUNTROLE, filters={"name__value": GENERAL_ACCESS_ROLE_NAME}
    )
    assert len(roles) == 1
    role = roles[0]
    peers = await role.permissions.get_peers(db=db, peer_type=Node)

    expected_pairs = {(namespace, name) for namespace, name, _ in PROPOSED_CHANGE_PERMISSIONS}
    matching: list[Node] = []
    for peer in peers.values():
        if peer.get_kind() != InfrahubKind.OBJECTPERMISSION:
            continue
        if (peer.namespace.value, peer.name.value) not in expected_pairs:
            continue
        action_value = peer.action.value
        decision_value = peer.decision.value
        action_str = action_value.value if hasattr(action_value, "value") else action_value
        decision_int = decision_value.value if hasattr(decision_value, "value") else decision_value
        if action_str != PermissionAction.ANY.value:
            continue
        if decision_int != PermissionDecision.ALLOW_ALL.value:
            continue
        matching.append(peer)
    return role, matching


async def test_migration_072_backfills_missing_permissions(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)

    _, initial_permissions = await _get_general_access_proposed_change_permissions(db=db)
    assert len(initial_permissions) == len(PROPOSED_CHANGE_PERMISSIONS)
    for permission in initial_permissions:
        await permission.delete(db=db)

    _, after_delete = await _get_general_access_proposed_change_permissions(db=db)
    assert after_delete == []

    migration = Migration072()
    result = await migration.execute(MigrationInput(db=db))
    assert result.success

    _, after_migration = await _get_general_access_proposed_change_permissions(db=db)
    assert {(p.namespace.value, p.name.value) for p in after_migration} == {
        (namespace, name) for namespace, name, _ in PROPOSED_CHANGE_PERMISSIONS
    }


async def test_migration_072_is_idempotent(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)

    migration = Migration072()
    first_run = await migration.execute(MigrationInput(db=db))
    assert first_run.success

    _, after_first_run = await _get_general_access_proposed_change_permissions(db=db)
    assert len(after_first_run) == len(PROPOSED_CHANGE_PERMISSIONS)
    first_run_ids = {p.id for p in after_first_run}

    second_run = await migration.execute(MigrationInput(db=db))
    assert second_run.success

    _, after_second_run = await _get_general_access_proposed_change_permissions(db=db)
    assert len(after_second_run) == len(PROPOSED_CHANGE_PERMISSIONS)
    assert {p.id for p in after_second_run} == first_run_ids


async def test_migration_072_skips_when_role_missing(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)

    roles = await NodeManager.query(
        db=db, schema=InfrahubKind.ACCOUNTROLE, filters={"name__value": GENERAL_ACCESS_ROLE_NAME}
    )
    assert len(roles) == 1
    role = roles[0]
    await role.delete(db=db)

    migration = Migration072()
    result = await migration.execute(MigrationInput(db=db))
    assert result.success

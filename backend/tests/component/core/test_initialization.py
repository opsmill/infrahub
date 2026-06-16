from uuid import UUID

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.initialization import first_time_initialization, get_root_node, reset_deployment_id
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_first_time_initialization(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)
    assert True


async def test_general_access_role_can_manage_proposed_changes(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)

    roles = await NodeManager.query(db=db, schema=InfrahubKind.ACCOUNTROLE, filters={"name__value": "General Access"})
    assert len(roles) == 1
    role = roles[0]
    permissions = await role.permissions.get_peers(db=db, peer_type=Node)

    expected_kinds = {
        ("Core", "ProposedChange"),
        ("Core", "ChangeComment"),
        ("Core", "ChangeThread"),
        ("Core", "ThreadComment"),
    }
    matching: set[tuple[str, str]] = set()
    for peer in permissions.values():
        if peer.get_kind() != InfrahubKind.OBJECTPERMISSION:
            continue
        peer_namespace = peer.namespace.value
        peer_name = peer.name.value
        if (peer_namespace, peer_name) not in expected_kinds:
            continue
        action_value = peer.action.value
        decision_value = peer.decision.value
        action_str = action_value.value if hasattr(action_value, "value") else action_value
        decision_int = decision_value.value if hasattr(decision_value, "value") else decision_value
        assert action_str == PermissionAction.ANY.value
        assert decision_int == PermissionDecision.ALLOW_ALL.value
        matching.add((peer_namespace, peer_name))
    assert matching == expected_kinds


async def test_reset_deployment_id_generates_new_uuid(db: InfrahubDatabase, default_branch: Branch) -> None:
    root_before = await get_root_node(db=db)
    original = str(root_before.get_uuid())

    old_uuid, new_uuid = await reset_deployment_id(db=db)

    assert old_uuid == original
    assert new_uuid != original
    UUID(new_uuid)

    root_after = await get_root_node(db=db)
    assert str(root_after.get_uuid()) == new_uuid


async def test_reset_deployment_id_with_explicit_value(db: InfrahubDatabase, default_branch: Branch) -> None:
    explicit = "11111111-2222-3333-4444-555555555555"

    _, new_uuid = await reset_deployment_id(db=db, new_uuid=explicit)

    assert new_uuid == explicit
    root_after = await get_root_node(db=db)
    assert str(root_after.get_uuid()) == explicit


async def test_reset_deployment_id_rejects_unchanged_value(db: InfrahubDatabase, default_branch: Branch) -> None:
    root = await get_root_node(db=db)
    current = str(root.get_uuid())

    with pytest.raises(ValueError, match="must be different"):
        await reset_deployment_id(db=db, new_uuid=current)

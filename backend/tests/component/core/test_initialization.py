from uuid import UUID

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.core.initialization import first_time_initialization, get_root_node, reset_deployment_id
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase


async def test_first_time_initialization(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)

    # The manage_global_preferences permission must be created
    permissions = await NodeManager.query(
        db=db,
        schema=InfrahubKind.GLOBALPERMISSION,
        filters={"action__value": GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value},
    )
    assert len(permissions) == 1

    # Exactly one empty CoreGlobalPreference singleton must be seeded
    preferences = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
    assert len(preferences) == 1
    assert preferences[0].date_format.value is None
    assert preferences[0].timezone.value is None


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

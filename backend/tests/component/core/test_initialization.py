from uuid import UUID

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_account,
    create_default_account_groups,
    first_time_initialization,
    get_root_node,
    reset_deployment_id,
)
from infrahub.core.manager import NodeManager
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.core.protocols import (
    CoreAccount,
    CoreAccountGroup,
    CoreAccountRole,
    CoreGlobalPermission,
    CoreObjectPermission,
)
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

EXPECTED_GLOBAL_PERMISSIONS = {
    "super_admin",
    "manage_repositories",
    "manage_schema",
    "merge_proposed_change",
    "edit_default_branch",
    "manage_accounts",
    "manage_global_preferences",
    "manage_permissions",
    "merge_branch",
    "rebase_branch",
    "review_proposed_change",
}


async def test_first_time_initialization(db: InfrahubDatabase, default_branch: Branch) -> None:
    await first_time_initialization(db=db)
    assert True


async def test_first_time_initialization_does_not_seed_preferences(
    db: InfrahubDatabase, delete_all_nodes_in_db: None
) -> None:
    """A fresh install seeds NO preference row.

    Preferences reads never create, and there is no init seed — a Preference row exists only after
    the first write.
    """
    # delete_all_nodes_in_db leaves a truly empty graph, so first_time_initialization runs against
    # a fresh install and builds its own Root.
    await first_time_initialization(db=db)

    assert await PreferenceRepository(db=db).get_all() == []


async def test_first_time_initialization_converges_core_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """A fresh installation must persist the schema shape the upgrade flow builds as its candidate.

    The candidate includes the deprecated overlay, so the core-schema diff starts out empty.
    """
    await first_time_initialization(db=db)

    branch_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    candidate_schema = branch_schema.duplicate()
    candidate_schema.load_schema(schema=SchemaRoot(**internal_schema))
    candidate_schema.load_schema(schema=SchemaRoot(**core_models))
    candidate_schema.load_schema(schema=SchemaRoot(**deprecated_models))
    candidate_schema.process()

    assert branch_schema.diff(other=candidate_schema).all == []


async def test_create_default_account_groups_creates_each_permission_once(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """The permissions are created concurrently, so a lost get-or-create would duplicate a node.

    Counts are asserted alongside the action names because a duplicate leaves the name set intact.
    """
    await create_default_account_groups(db=db)

    global_permissions = await NodeManager.query(db=db, schema=CoreGlobalPermission)
    assert {permission.action.value for permission in global_permissions} == EXPECTED_GLOBAL_PERMISSIONS
    assert len(global_permissions) == len(EXPECTED_GLOBAL_PERMISSIONS)

    object_permissions = await NodeManager.query(db=db, schema=CoreObjectPermission)
    assert {
        (
            permission.namespace.value,
            permission.name.value,
            permission.action.value.value,
            permission.decision.value.value,
        )
        for permission in object_permissions
    } == {
        ("*", "*", "view", 6),
        ("*", "*", "any", 4),
        ("Core", "ProposedChange", "update", 6),
    }
    assert len(object_permissions) == 3

    roles = await NodeManager.query(db=db, schema=CoreAccountRole)
    assert {role.name.value for role in roles} == {
        "Super Administrator",
        "General Access",
        "Proposed Change Reviewer",
    }
    assert len(roles) == 3


async def test_create_default_account_groups_assigns_every_member(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    admin = await create_account(db=db, name="admin-1", password="Testing1234", token_value=None)
    bot = await create_account(db=db, name="bot-1", password="Testing1234", token_value=None)
    user = await create_account(db=db, name="user-1", password="Testing1234", token_value=None)

    await create_default_account_groups(db=db, admin_accounts=[admin, bot], accounts=[user])

    groups = {group.name.value: group for group in await NodeManager.query(db=db, schema=CoreAccountGroup)}
    assert set(groups) == {"Super Administrators", "Infrahub Users"}

    admin_members = await groups["Super Administrators"].members.get_peers(db=db, peer_type=CoreAccount)
    assert {member.id for member in admin_members.values()} == {admin.id, bot.id}

    user_members = await groups["Infrahub Users"].members.get_peers(db=db, peer_type=CoreAccount)
    assert {member.id for member in user_members.values()} == {user.id}


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

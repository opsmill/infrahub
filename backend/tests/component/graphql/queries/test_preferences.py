from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.preferences import GlobalPreference, UserPreference
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

EFFECTIVE_QUERY = """
query {
  InfrahubEffectivePreferences {
    date_format
    timezone
    can_edit_global_preferences
  }
}
"""


async def run_effective(
    db: InfrahubDatabase, branch: Branch, account_session: AccountSession | None
) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    return await graphql(
        schema=gql_params.schema,
        source=EFFECTIVE_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


async def _grant_manage_global_preferences(db: InfrahubDatabase, account: Node) -> None:
    """Assign the manage_global_preferences global permission to `account` via a role + group."""
    permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await permission.new(
        db=db,
        action=GlobalPermissions.MANAGE_GLOBAL_PREFERENCES.value,
        decision=PermissionDecision.ALLOW_ALL.value,
    )
    await permission.save(db=db)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="prefs-manager", permissions=[permission])
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="prefs-managers", roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": account.id})
    await group.members.save(db=db)


async def test_effective_no_global_no_user(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    data = result.data["InfrahubEffectivePreferences"]
    assert data["date_format"] is None
    assert data["timezone"] is None
    # A fresh-user read lazily materialises the global singleton but never a UserPreference row.
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None


async def test_effective_global_only_fresh_user_fallback(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    global_pref = await GlobalPreference.get_global(db=db)
    global_pref.date_format = "yyyy-MM-dd"
    global_pref.timezone = "UTC"
    await global_pref.save(db=db)

    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    data = result.data["InfrahubEffectivePreferences"]
    assert data["date_format"] == "yyyy-MM-dd"
    assert data["timezone"] == "UTC"
    # No user row was fabricated for the fallback.
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None


async def test_effective_user_overrides_and_per_field_merge(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    global_pref = await GlobalPreference.get_global(db=db)
    global_pref.date_format = "yyyy-MM-dd"
    global_pref.timezone = "UTC"
    await global_pref.save(db=db)

    # User overrides only date_format; timezone falls back to global.
    user_pref = UserPreference(account_id=first_account.id, date_format="dd/MM/yyyy")
    await user_pref.create(db=db)

    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    data = result.data["InfrahubEffectivePreferences"]
    assert data["date_format"] == "dd/MM/yyyy"  # user override wins
    assert data["timezone"] == "UTC"  # per-field fallback to global


async def test_effective_is_private_per_caller(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    second_account: Node,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    # Account A sets a personal override.
    await UserPreference(account_id=first_account.id, timezone="Europe/Paris").create(db=db)
    # Account B sets a different one.
    await UserPreference(account_id=second_account.id, timezone="America/New_York").create(db=db)

    result_a = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    result_b = await run_effective(db=db, branch=default_branch, account_session=session_second_account)
    assert result_a.errors is None
    assert result_b.errors is None
    # Each caller sees only their own value; A never sees B's.
    assert result_a.data["InfrahubEffectivePreferences"]["timezone"] == "Europe/Paris"
    assert result_b.data["InfrahubEffectivePreferences"]["timezone"] == "America/New_York"


async def test_effective_can_edit_false_for_normal_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    assert result.data["InfrahubEffectivePreferences"]["can_edit_global_preferences"] is False


async def test_effective_can_edit_true_for_manager(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    first_account: Node,
) -> None:
    await _grant_manage_global_preferences(db=db, account=first_account)
    session = AccountSession(authenticated=True, auth_type=AuthType.JWT, account_id=first_account.id)

    result = await run_effective(db=db, branch=default_branch, account_session=session)
    assert result.errors is None
    assert result.data["InfrahubEffectivePreferences"]["can_edit_global_preferences"] is True


async def test_effective_can_edit_true_for_super_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    create_test_admin: Node,
    session_admin: AccountSession,
) -> None:
    result = await run_effective(db=db, branch=default_branch, account_session=session_admin)
    assert result.errors is None
    assert result.data["InfrahubEffectivePreferences"]["can_edit_global_preferences"] is True

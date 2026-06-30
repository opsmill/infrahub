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
    preferences {
      key
      value
      source
    }
    global {
      date_format
      timezone
    }
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


def _entries_by_key(data: dict) -> dict[str, dict]:
    """Index the `preferences` list by its `key` for easy per-attribute assertions."""
    return {entry["key"]: entry for entry in data["preferences"]}


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

    await group.members.add(db=db, data={"id": account.id})  # type: ignore[attr-defined]
    await group.members.save(db=db)  # type: ignore[attr-defined]


async def test_effective_no_global_no_user(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    data = result.data["InfrahubEffectivePreferences"]
    entries = _entries_by_key(data)
    # Nothing defined anywhere: every entry resolves to value null, source DEFAULT.
    assert entries["date_format"] == {"key": "date_format", "value": None, "source": "DEFAULT"}
    assert entries["timezone"] == {"key": "timezone", "value": None, "source": "DEFAULT"}
    # The raw org-defaults block is empty too.
    assert data["global"] == {"date_format": None, "timezone": None}
    # A fresh-user read lazily materialises the global singleton but never a UserPreference row.
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None


async def test_effective_global_only_source_global(
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
    assert result.data is not None
    data = result.data["InfrahubEffectivePreferences"]
    entries = _entries_by_key(data)
    # No user override: resolved value comes from global, source GLOBAL.
    assert entries["date_format"] == {"key": "date_format", "value": "yyyy-MM-dd", "source": "GLOBAL"}
    assert entries["timezone"] == {"key": "timezone", "value": "UTC", "source": "GLOBAL"}
    # The raw org-defaults block mirrors the singleton.
    assert data["global"] == {"date_format": "yyyy-MM-dd", "timezone": "UTC"}
    # No user row was fabricated for the fallback.
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None


async def test_effective_user_override_source_user(
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

    await UserPreference(account_id=first_account.id, date_format="dd/MM/yyyy", timezone="Europe/Paris").create(db=db)

    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    data = result.data["InfrahubEffectivePreferences"]
    entries = _entries_by_key(data)
    # User override wins for both attributes: source USER, value is the user's.
    assert entries["date_format"] == {"key": "date_format", "value": "dd/MM/yyyy", "source": "USER"}
    assert entries["timezone"] == {"key": "timezone", "value": "Europe/Paris", "source": "USER"}
    # The raw org-defaults block still reports the org value, unaffected by the override.
    assert data["global"] == {"date_format": "yyyy-MM-dd", "timezone": "UTC"}


async def test_effective_mixed_per_attribute_sources(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Per-attribute resolution: one USER, one GLOBAL, one DEFAULT — all in a single read."""
    global_pref = await GlobalPreference.get_global(db=db)
    # Global defines timezone only; date_format is left unset on the singleton.
    global_pref.timezone = "UTC"
    await global_pref.save(db=db)

    # User overrides date_format only; timezone falls back to global.
    await UserPreference(account_id=first_account.id, date_format="dd/MM/yyyy").create(db=db)

    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    data = result.data["InfrahubEffectivePreferences"]
    entries = _entries_by_key(data)
    # date_format: user override present -> USER.
    assert entries["date_format"] == {"key": "date_format", "value": "dd/MM/yyyy", "source": "USER"}
    # timezone: no user override, global present -> GLOBAL.
    assert entries["timezone"] == {"key": "timezone", "value": "UTC", "source": "GLOBAL"}
    assert data["global"] == {"date_format": None, "timezone": "UTC"}


async def test_effective_admin_override_global_block_keeps_org_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """An admin with a personal override: the `global` block must still report the raw org value.

    The "Organisation defaults" editor relies on the `global` block (not the resolved
    `preferences` value) so it edits the org-wide default rather than the admin's override.
    """
    global_pref = await GlobalPreference.get_global(db=db)
    global_pref.timezone = "UTC"
    await global_pref.save(db=db)

    await UserPreference(account_id=first_account.id, timezone="Europe/Paris").create(db=db)

    result = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    data = result.data["InfrahubEffectivePreferences"]
    entries = _entries_by_key(data)
    # Resolved preference reflects the admin's own override.
    assert entries["timezone"] == {"key": "timezone", "value": "Europe/Paris", "source": "USER"}
    # But the org-defaults block keeps the raw org value, what the defaults editor edits.
    assert data["global"]["timezone"] == "UTC"


async def test_effective_is_private_per_caller(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    second_account: Node,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    # A shared org-wide default exists.
    global_pref = await GlobalPreference.get_global(db=db)
    global_pref.timezone = "UTC"
    await global_pref.save(db=db)
    # Account A sets a personal override.
    await UserPreference(account_id=first_account.id, timezone="Europe/Paris").create(db=db)
    # Account B sets a different personal override.
    await UserPreference(account_id=second_account.id, timezone="America/New_York").create(db=db)

    result_a = await run_effective(db=db, branch=default_branch, account_session=session_first_account)
    result_b = await run_effective(db=db, branch=default_branch, account_session=session_second_account)
    assert result_a.errors is None
    assert result_b.errors is None
    assert result_a.data is not None
    assert result_b.data is not None
    entries_a = _entries_by_key(result_a.data["InfrahubEffectivePreferences"])
    entries_b = _entries_by_key(result_b.data["InfrahubEffectivePreferences"])
    # Each caller sees only their own resolved value, sourced USER; A never sees B's.
    assert entries_a["timezone"] == {"key": "timezone", "value": "Europe/Paris", "source": "USER"}
    assert entries_b["timezone"] == {"key": "timezone", "value": "America/New_York", "source": "USER"}
    # The org-defaults block is org-wide and identical for both sessions.
    assert result_a.data["InfrahubEffectivePreferences"]["global"]["timezone"] == "UTC"
    assert result_b.data["InfrahubEffectivePreferences"]["global"]["timezone"] == "UTC"


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
    assert result.data is not None
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
    assert result.data is not None
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
    assert result.data is not None
    assert result.data["InfrahubEffectivePreferences"]["can_edit_global_preferences"] is True


async def test_effective_rejects_anonymous(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
) -> None:
    # No account session at all: rejected.
    result = await run_effective(db=db, branch=default_branch, account_session=None)
    assert result.errors is not None
    assert any("authenticated account" in str(error) for error in result.errors)

    # Unauthenticated/anonymous session: also rejected.
    anonymous = AccountSession(authenticated=False, auth_type=AuthType.NONE, account_id="")
    result = await run_effective(db=db, branch=default_branch, account_session=anonymous)
    assert result.errors is not None
    assert any("authenticated account" in str(error) for error in result.errors)

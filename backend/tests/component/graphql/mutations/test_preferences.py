from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

SET_PREFERENCES = """
mutation ($scope: PreferenceScope!, $date_format: DateFormat, $timezone: String) {
  InfrahubSetPreferences(scope: $scope, date_format: $date_format, timezone: $timezone) {
    ok
    date_format
    timezone
  }
}
"""


async def run_mutation(
    db: InfrahubDatabase,
    branch: Branch,
    account_session: AccountSession | None,
    variables: dict[str, Any],
) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, include_mutation=True, branch=branch, account_session=account_session
    )
    return await graphql(
        schema=gql_params.schema,
        source=SET_PREFERENCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def _grant_manage_global_preferences(db: InfrahubDatabase, account: Node) -> None:
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


# --------------------------------------------------------------------------------------------
# scope=USER — caller's OWN row only; lazy create + idempotent; explicit-null reset.
# --------------------------------------------------------------------------------------------
async def test_user_lazy_create_then_update(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None

    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "date_format": "EU_DATETIME", "timezone": "Europe/Paris"},
    )
    assert result.errors is None
    assert result.data["InfrahubSetPreferences"]["ok"] is True
    assert result.data["InfrahubSetPreferences"]["date_format"] == "EU_DATETIME"

    created = await UserPreference.get_for_account(db=db, account_id=first_account.id)
    assert created is not None
    assert created.timezone == "Europe/Paris"

    # Second call updates the same row (idempotent — no second row).
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "timezone": "UTC"},
    )
    assert result.errors is None
    assert result.data["InfrahubSetPreferences"]["timezone"] == "UTC"

    updated = await UserPreference.get_for_account(db=db, account_id=first_account.id)
    assert updated is not None
    assert updated.uuid == created.uuid
    assert updated.timezone == "UTC"
    assert updated.date_format == "EU_DATETIME"  # unchanged field preserved
    rows = [p for p in await UserPreference.get_list(db=db) if p.account_id == first_account.id]
    assert len(rows) == 1


async def test_user_repeated_never_creates_second_row(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Repeated upserts for one account always target the single locked row."""
    for tz in ("Europe/Paris", "UTC", "America/New_York", "Asia/Tokyo"):
        result = await run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            variables={"scope": "USER", "timezone": tz},
        )
        assert result.errors is None

    rows = [p for p in await UserPreference.get_list(db=db) if p.account_id == first_account.id]
    assert len(rows) == 1
    assert rows[0].timezone == "Asia/Tokyo"


async def test_user_explicit_null_resets_field(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """An explicit null clears a field, while an omitted argument leaves it unchanged."""
    await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "date_format": "EU_DATETIME", "timezone": "Europe/Paris"},
    )

    # Explicit null on date_format resets it; timezone omitted stays unchanged.
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "date_format": None},
    )
    assert result.errors is None
    assert result.data["InfrahubSetPreferences"]["date_format"] is None
    assert result.data["InfrahubSetPreferences"]["timezone"] == "Europe/Paris"

    reset = await UserPreference.get_for_account(db=db, account_id=first_account.id)
    assert reset is not None
    assert reset.date_format is None
    assert reset.timezone == "Europe/Paris"


async def test_user_two_accounts_distinct_rows(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    second_account: Node,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    # No account argument exists on the mutation: each caller can only ever write its own row.
    await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "timezone": "Europe/Paris"},
    )
    await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_second_account,
        variables={"scope": "USER", "timezone": "America/New_York"},
    )

    pref_a = await UserPreference.get_for_account(db=db, account_id=first_account.id)
    pref_b = await UserPreference.get_for_account(db=db, account_id=second_account.id)
    assert pref_a is not None
    assert pref_b is not None
    assert pref_a.uuid != pref_b.uuid
    assert pref_a.timezone == "Europe/Paris"
    assert pref_b.timezone == "America/New_York"


async def test_user_rejects_unauthenticated(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
) -> None:
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=None,
        variables={"scope": "USER", "timezone": "UTC"},
    )
    assert result.errors is not None
    assert "authenticated" in str(result.errors[0].message).lower()


async def test_user_rejects_unknown_date_format(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Reject an unknown date_format at the GraphQL layer.

    date_format is a DateFormat enum, so an unknown semantic key is rejected before any write and no
    UserPreference row is created.
    """
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "date_format": "NOT_A_FORMAT"},
    )
    assert result.errors is not None
    # Specifically the DateFormat enum-validation error for the bad value — not some unrelated
    # failure that would also leave no row behind.
    messages = " ".join(str(error.message) for error in result.errors)
    assert "NOT_A_FORMAT" in messages or "DateFormat" in messages, messages
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None


# --------------------------------------------------------------------------------------------
# scope=GLOBAL — gated on manage_global_preferences; nothing written when denied.
# --------------------------------------------------------------------------------------------
async def test_global_denied_for_normal_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "GLOBAL", "date_format": "ISO_DATETIME"},
    )
    assert result.errors is not None
    # The singleton must not have been mutated (gate raises BEFORE the read-modify-write).
    global_pref = await GlobalPreference.get_global(db=db)
    assert global_pref.date_format is None


async def test_global_allowed_for_manager(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    first_account: Node,
) -> None:
    await _grant_manage_global_preferences(db=db, account=first_account)
    session = AccountSession(authenticated=True, auth_type=AuthType.JWT, account_id=first_account.id)

    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session,
        variables={"scope": "GLOBAL", "date_format": "ISO_DATETIME", "timezone": "UTC"},
    )
    assert result.errors is None
    assert result.data["InfrahubSetPreferences"]["ok"] is True

    global_pref = await GlobalPreference.get_global(db=db)
    assert global_pref.date_format == "ISO_DATETIME"
    assert global_pref.timezone == "UTC"
    assert len(await GlobalPreference.get_list(db=db)) == 1


async def test_global_allowed_for_super_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    create_test_admin: Node,
    session_admin: AccountSession,
) -> None:
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        variables={"scope": "GLOBAL", "timezone": "Europe/London"},
    )
    assert result.errors is None
    assert result.data["InfrahubSetPreferences"]["ok"] is True

    global_pref = await GlobalPreference.get_global(db=db)
    assert global_pref.timezone == "Europe/London"


async def test_global_preserves_other_field(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    create_test_admin: Node,
    session_admin: AccountSession,
) -> None:
    """Two separate updates of different fields accumulate; neither clobbers the other.

    Each update is a serialized read-modify-write under the singleton lock, so updating only
    `timezone` re-reads the row and leaves a previously-set `date_format` intact (no lost write).
    This verifies the read-modify-write is field-preserving across sequential updates (what the
    lock guarantees under concurrency); it does not itself run concurrent writers.
    """
    await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        variables={"scope": "GLOBAL", "date_format": "ISO_DATETIME"},
    )
    await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        variables={"scope": "GLOBAL", "timezone": "UTC"},
    )

    global_pref = await GlobalPreference.get_global(db=db)
    assert global_pref.date_format == "ISO_DATETIME"  # preserved across the second update
    assert global_pref.timezone == "UTC"
    assert len(await GlobalPreference.get_list(db=db)) == 1


# --------------------------------------------------------------------------------------------
# scope=EFFECTIVE — read-only, never writable.
# --------------------------------------------------------------------------------------------
async def test_effective_scope_rejected(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "EFFECTIVE", "timezone": "UTC"},
    )
    assert result.errors is not None
    assert "read-only" in str(result.errors[0].message).lower()
    # Nothing was written for the caller.
    assert await UserPreference.get_for_account(db=db, account_id=first_account.id) is None

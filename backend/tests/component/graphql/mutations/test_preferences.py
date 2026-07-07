from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

SET_PREFERENCES = """
mutation ($scope: PreferenceWriteScope!, $date_format: DateFormat, $timezone: String) {
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
    # No row exists until the first write (writes are the only create path).
    assert await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id) is None

    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "date_format": "EU_DATETIME", "timezone": "Europe/Paris"},
    )
    assert result.errors is None
    assert result.data is not None
    assert result.data["InfrahubSetPreferences"]["ok"] is True
    assert result.data["InfrahubSetPreferences"]["date_format"] == "EU_DATETIME"

    created = await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id)
    assert created is not None
    assert created.timezone == "Europe/Paris"

    # Second call updates the same row (idempotent — no second row for this owner).
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "timezone": "UTC"},
    )
    assert result.errors is None
    assert result.data is not None
    assert result.data["InfrahubSetPreferences"]["timezone"] == "UTC"

    updated = await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id)
    assert updated is not None
    assert updated.uuid == created.uuid
    assert updated.timezone == "UTC"
    assert updated.date_format == "EU_DATETIME"  # omitted field preserved


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
    assert result.data is not None
    assert result.data["InfrahubSetPreferences"]["date_format"] is None
    assert result.data["InfrahubSetPreferences"]["timezone"] == "Europe/Paris"

    reset = await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id)
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
    # No account argument on the mutation: each caller can only ever write its own row.
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

    pref_a = await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id)
    pref_b = await PreferenceRepository(db=db).get_for_owner(owner_id=second_account.id)
    assert pref_a is not None
    assert pref_b is not None
    assert pref_a.uuid != pref_b.uuid
    assert pref_a.timezone == "Europe/Paris"
    assert pref_b.timezone == "America/New_York"


async def test_user_rejects_unknown_date_format(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Reject an unknown date_format at the GraphQL layer.

    date_format is a DateFormat enum, so an unknown semantic key is rejected before any write and no
    Preference row is created.
    """
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "USER", "date_format": "NOT_A_FORMAT"},
    )
    assert result.errors is not None
    # Specifically the DateFormat enum-coercion error for the bad value.
    messages = " ".join(str(error.message) for error in result.errors)
    assert "NOT_A_FORMAT" in messages or "DateFormat" in messages, messages
    assert await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id) is None


async def test_rejects_effective_scope_enum_value(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """PreferenceWriteScope has no EFFECTIVE member, so scope:EFFECTIVE fails enum coercion."""
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
        variables={"scope": "EFFECTIVE", "timezone": "UTC"},
    )
    assert result.errors is not None
    # No row was written for the caller.
    assert await PreferenceRepository(db=db).get_for_owner(owner_id=first_account.id) is None


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
    # Nothing written: the gate raises BEFORE the read-modify-write, so no global row exists.
    assert await PreferenceRepository(db=db).get_for_owner(owner_id=registry.id) is None


async def test_global_allowed_for_manager(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    session_global_prefs_manager: AccountSession,
) -> None:
    result = await run_mutation(
        db=db,
        branch=default_branch,
        account_session=session_global_prefs_manager,
        variables={"scope": "GLOBAL", "date_format": "ISO_DATETIME", "timezone": "UTC"},
    )
    assert result.errors is None
    assert result.data is not None
    assert result.data["InfrahubSetPreferences"]["ok"] is True

    global_pref = await PreferenceRepository(db=db).get_for_owner(owner_id=registry.id)
    assert global_pref is not None
    assert global_pref.date_format == "ISO_DATETIME"
    assert global_pref.timezone == "UTC"


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
    assert result.data is not None
    assert result.data["InfrahubSetPreferences"]["ok"] is True

    global_pref = await PreferenceRepository(db=db).get_for_owner(owner_id=registry.id)
    assert global_pref is not None
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

    Each update is a serialized read-modify-write under the per-owner lock, so updating only
    `timezone` re-reads the row and leaves a previously-set `date_format` intact (no lost write).
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

    global_pref = await PreferenceRepository(db=db).get_for_owner(owner_id=registry.id)
    assert global_pref is not None
    assert global_pref.date_format == "ISO_DATETIME"  # preserved across the second update
    assert global_pref.timezone == "UTC"

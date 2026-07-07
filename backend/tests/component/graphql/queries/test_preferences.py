from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.preferences.models import Preference
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

EFFECTIVE_QUERY = """
query {
  InfrahubEffectivePreferences {
    date_format { value source }
    timezone { value source }
  }
}
"""

USER_QUERY = """
query {
  InfrahubUserPreferences {
    date_format
    timezone
  }
}
"""

GLOBAL_QUERY = """
query {
  InfrahubGlobalPreferences {
    date_format
    timezone
  }
}
"""


async def run_query(
    db: InfrahubDatabase,
    branch: Branch,
    query: str,
    account_session: AccountSession | None,
) -> ExecutionResult:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )


# --------------------------------------------------------------------------------------------
# InfrahubEffectivePreferences — merged user -> global -> default; open to any authenticated caller.
# --------------------------------------------------------------------------------------------
async def test_effective_no_user_no_global_is_default(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # Nothing defined anywhere: value null, source DEFAULT.
    assert prefs["date_format"] == {"value": None, "source": "DEFAULT"}
    assert prefs["timezone"] == {"value": None, "source": "DEFAULT"}
    # A read never fabricates a row.
    assert await Preference.get_for_owner(db=db, owner_id=first_account.id) is None


async def test_effective_global_only_source_global(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    await Preference(owner_id=registry.id, date_format="ISO_DATETIME", timezone="UTC").create(db=db)

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # No user override: resolved value comes from the global row, source GLOBAL.
    assert prefs["date_format"] == {"value": "ISO_DATETIME", "source": "GLOBAL"}
    assert prefs["timezone"] == {"value": "UTC", "source": "GLOBAL"}
    # No user row was fabricated for the fallback.
    assert await Preference.get_for_owner(db=db, owner_id=first_account.id) is None


async def test_effective_user_override_source_user(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    await Preference(owner_id=registry.id, date_format="ISO_DATETIME", timezone="UTC").create(db=db)
    await Preference(owner_id=first_account.id, date_format="EU_DATETIME", timezone="Europe/Paris").create(db=db)

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # User override wins for both attributes: source USER, value is the user's.
    assert prefs["date_format"] == {"value": "EU_DATETIME", "source": "USER"}
    assert prefs["timezone"] == {"value": "Europe/Paris", "source": "USER"}


async def test_effective_mixed_per_attribute_sources(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Per-attribute resolution: one USER, one GLOBAL, one DEFAULT in a single read."""
    # Global defines timezone only; date_format is left unset on the global row.
    await Preference(owner_id=registry.id, timezone="UTC").create(db=db)
    # User overrides date_format only; timezone falls back to global.
    await Preference(owner_id=first_account.id, date_format="EU_DATETIME").create(db=db)

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # date_format: user override present -> USER.
    assert prefs["date_format"] == {"value": "EU_DATETIME", "source": "USER"}
    # timezone: no user override, global present -> GLOBAL.
    assert prefs["timezone"] == {"value": "UTC", "source": "GLOBAL"}


async def test_effective_is_private_per_caller(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    second_account: Node,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    # A shared org-wide default plus a distinct personal override for each account.
    await Preference(owner_id=registry.id, timezone="UTC").create(db=db)
    await Preference(owner_id=first_account.id, timezone="Europe/Paris").create(db=db)
    await Preference(owner_id=second_account.id, timezone="America/New_York").create(db=db)

    result_a = await run_query(
        db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account
    )
    result_b = await run_query(
        db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_second_account
    )
    assert result_a.errors is None
    assert result_b.errors is None
    assert result_a.data is not None
    assert result_b.data is not None
    # Each caller sees only their own resolved value, sourced USER; A never sees B's.
    assert result_a.data["InfrahubEffectivePreferences"]["timezone"] == {
        "value": "Europe/Paris",
        "source": "USER",
    }
    assert result_b.data["InfrahubEffectivePreferences"]["timezone"] == {
        "value": "America/New_York",
        "source": "USER",
    }


# --------------------------------------------------------------------------------------------
# InfrahubUserPreferences — caller's OWN raw values, null where unset; account-bound.
# --------------------------------------------------------------------------------------------
async def test_user_returns_own_raw_values_null_where_unset(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    # A global default exists but must NOT leak into a USER read.
    await Preference(owner_id=registry.id, timezone="UTC").create(db=db)
    await Preference(owner_id=first_account.id, date_format="EU_DATETIME").create(db=db)

    result = await run_query(db=db, branch=default_branch, query=USER_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubUserPreferences"]
    # date_format is the user's own raw value; timezone is unset for THIS user -> null (no bleed).
    assert prefs["date_format"] == "EU_DATETIME"
    assert prefs["timezone"] is None


async def test_user_never_sees_other_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    second_account: Node,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    await Preference(owner_id=first_account.id, timezone="Europe/Paris").create(db=db)
    await Preference(owner_id=second_account.id, timezone="America/New_York").create(db=db)

    result_a = await run_query(db=db, branch=default_branch, query=USER_QUERY, account_session=session_first_account)
    result_b = await run_query(db=db, branch=default_branch, query=USER_QUERY, account_session=session_second_account)
    assert result_a.errors is None
    assert result_b.errors is None
    assert result_a.data is not None
    assert result_b.data is not None
    # Each caller sees ONLY their own raw value; no cross-account bleed.
    assert result_a.data["InfrahubUserPreferences"]["timezone"] == "Europe/Paris"
    assert result_b.data["InfrahubUserPreferences"]["timezone"] == "America/New_York"


# --------------------------------------------------------------------------------------------
# InfrahubGlobalPreferences — org-wide raw values; gated on manage_global_preferences.
# --------------------------------------------------------------------------------------------
async def test_global_allowed_for_manager(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    session_global_prefs_manager: AccountSession,
) -> None:
    await Preference(owner_id=registry.id, date_format="ISO_DATETIME", timezone="UTC").create(db=db)

    result = await run_query(
        db=db, branch=default_branch, query=GLOBAL_QUERY, account_session=session_global_prefs_manager
    )
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubGlobalPreferences"]
    # Raw org values (no source — the scope IS the source).
    assert prefs["date_format"] == "ISO_DATETIME"
    assert prefs["timezone"] == "UTC"


async def test_global_allowed_for_super_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    create_test_admin: Node,
    session_admin: AccountSession,
) -> None:
    await Preference(owner_id=registry.id, timezone="Europe/London").create(db=db)

    result = await run_query(db=db, branch=default_branch, query=GLOBAL_QUERY, account_session=session_admin)
    assert result.errors is None
    assert result.data is not None
    assert result.data["InfrahubGlobalPreferences"]["timezone"] == "Europe/London"


async def test_global_denied_for_normal_account(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    # A global row exists, but a normal account must be denied and see no data.
    await Preference(owner_id=registry.id, timezone="UTC").create(db=db)

    result = await run_query(db=db, branch=default_branch, query=GLOBAL_QUERY, account_session=session_first_account)
    assert result.errors is not None
    assert result.data is None or result.data.get("InfrahubGlobalPreferences") is None

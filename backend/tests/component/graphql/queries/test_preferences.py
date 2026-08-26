from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.preferences.constants import GLOBAL_OWNER_ID
from infrahub.core.preferences.models import Preference
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

# `inherited` is selected on every effective read rather than by a second query constant: an additive
# field is a GraphQL non-breakage guarantee no test constant could prove, and selecting it everywhere
# pins `source != USER => inherited == {value, source}` on all of the paths below.
EFFECTIVE_QUERY = """
query {
  InfrahubEffectivePreferences {
    date_format { value source inherited { value source } }
    timezone { value source inherited { value source } }
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
    session_first_account: AccountSession,
) -> None:
    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # Nothing defined anywhere: value null, source DEFAULT, and nothing to inherit either.
    assert prefs["date_format"] == {
        "value": None,
        "source": "DEFAULT",
        "inherited": {"value": None, "source": "DEFAULT"},
    }
    assert prefs["timezone"] == {
        "value": None,
        "source": "DEFAULT",
        "inherited": {"value": None, "source": "DEFAULT"},
    }


async def test_effective_global_only_source_global(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    session_first_account: AccountSession,
) -> None:
    await PreferenceRepository(db=db).save(
        Preference(owner_id=GLOBAL_OWNER_ID, date_format="ISO_DATETIME", timezone="UTC")
    )

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # No user override: resolved value comes from the global row, source GLOBAL. Nothing is being
    # shadowed, so the inherited layer is the resolved one — the invariant, restated on the wire.
    assert prefs["date_format"] == {
        "value": "ISO_DATETIME",
        "source": "GLOBAL",
        "inherited": {"value": "ISO_DATETIME", "source": "GLOBAL"},
    }
    assert prefs["timezone"] == {
        "value": "UTC",
        "source": "GLOBAL",
        "inherited": {"value": "UTC", "source": "GLOBAL"},
    }


async def test_effective_user_override_source_user(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    await PreferenceRepository(db=db).save(
        Preference(owner_id=GLOBAL_OWNER_ID, date_format="ISO_DATETIME", timezone="UTC")
    )
    await PreferenceRepository(db=db).save(
        Preference(owner_id=first_account.id, date_format="EU_DATETIME", timezone="Europe/Paris")
    )

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # User override wins for both attributes: source USER, value is the user's. The shadowed global
    # layer stays readable as `inherited` — this is the case #10200 needed, so a client can preview
    # what clearing the override would fall back to without re-reading the (gated) org row.
    assert prefs["date_format"] == {
        "value": "EU_DATETIME",
        "source": "USER",
        "inherited": {"value": "ISO_DATETIME", "source": "GLOBAL"},
    }
    assert prefs["timezone"] == {
        "value": "Europe/Paris",
        "source": "USER",
        "inherited": {"value": "UTC", "source": "GLOBAL"},
    }


async def test_effective_mixed_per_attribute_sources(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Attributes resolve independently: an override on one attribute leaves the other's fallback untouched."""
    # Global defines timezone only; date_format is left unset on the global row.
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, timezone="UTC"))
    # User overrides date_format only; timezone falls back to global.
    await PreferenceRepository(db=db).save(Preference(owner_id=first_account.id, date_format="EU_DATETIME"))

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # date_format: user override present -> USER, and it shadows nothing (the global row leaves the
    # field unset), so the inherited layer is DEFAULT.
    assert prefs["date_format"] == {
        "value": "EU_DATETIME",
        "source": "USER",
        "inherited": {"value": None, "source": "DEFAULT"},
    }
    # timezone: no user override, global present -> GLOBAL, inheriting itself.
    assert prefs["timezone"] == {
        "value": "UTC",
        "source": "GLOBAL",
        "inherited": {"value": "UTC", "source": "GLOBAL"},
    }


async def test_effective_mixed_inherited_layers_per_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """The inherited layer is resolved per attribute too: two USER-sourced fields can inherit differently.

    Both fields are overridden, so both report USER, but only date_format shadows an org default. A
    client cannot infer one field's inherited layer from the other's, nor from the resolved source.
    """
    # Global defines date_format only.
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, date_format="ISO_DATETIME"))
    # User overrides both.
    await PreferenceRepository(db=db).save(
        Preference(owner_id=first_account.id, date_format="EU_DATETIME", timezone="Europe/Paris")
    )

    result = await run_query(db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account)
    assert result.errors is None
    assert result.data is not None
    prefs = result.data["InfrahubEffectivePreferences"]
    # USER shadowing GLOBAL: clearing this override would land on the org default.
    assert prefs["date_format"] == {
        "value": "EU_DATETIME",
        "source": "USER",
        "inherited": {"value": "ISO_DATETIME", "source": "GLOBAL"},
    }
    # USER shadowing nothing: clearing this override would land on the client's own default.
    assert prefs["timezone"] == {
        "value": "Europe/Paris",
        "source": "USER",
        "inherited": {"value": None, "source": "DEFAULT"},
    }


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
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, timezone="UTC"))
    await PreferenceRepository(db=db).save(Preference(owner_id=first_account.id, timezone="Europe/Paris"))
    await PreferenceRepository(db=db).save(Preference(owner_id=second_account.id, timezone="America/New_York"))

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
    # Each caller sees only their own resolved value, sourced USER; A never sees B's. What the two DO
    # share is the inherited layer: the org default is common to everyone by design, so disclosing it
    # here leaks nothing personal — the private part is the override, and that stays per-caller.
    assert result_a.data["InfrahubEffectivePreferences"]["timezone"] == {
        "value": "Europe/Paris",
        "source": "USER",
        "inherited": {"value": "UTC", "source": "GLOBAL"},
    }
    assert result_b.data["InfrahubEffectivePreferences"]["timezone"] == {
        "value": "America/New_York",
        "source": "USER",
        "inherited": {"value": "UTC", "source": "GLOBAL"},
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
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, timezone="UTC"))
    await PreferenceRepository(db=db).save(Preference(owner_id=first_account.id, date_format="EU_DATETIME"))

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
    await PreferenceRepository(db=db).save(Preference(owner_id=first_account.id, timezone="Europe/Paris"))
    await PreferenceRepository(db=db).save(Preference(owner_id=second_account.id, timezone="America/New_York"))

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
    await PreferenceRepository(db=db).save(
        Preference(owner_id=GLOBAL_OWNER_ID, date_format="ISO_DATETIME", timezone="UTC")
    )

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
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, timezone="Europe/London"))

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
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, timezone="UTC"))

    result = await run_query(db=db, branch=default_branch, query=GLOBAL_QUERY, account_session=session_first_account)
    assert result.errors is not None
    assert result.data is None or result.data.get("InfrahubGlobalPreferences") is None


async def test_effective_inherited_readable_without_manage_global_permission(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """The asymmetry between the two queries is deliberate, not an oversight.

    `session_first_account` holds no role, group or permission, so the gated raw org read is denied.
    The effective read still reports the org's timezone as this caller's `inherited` layer, because
    that value already had to be disclosed for every field the caller does not override (it would
    simply be labelled GLOBAL instead). `inherited` therefore widens no boundary: what stays gated is
    the raw org row as a row — every field at once, including fields nobody has inherited.

    `default_permission_backend` is mandatory. Without it the permission backend may be inactive, the
    gate would never raise, and the first half of this test would prove nothing.
    """
    await PreferenceRepository(db=db).save(Preference(owner_id=GLOBAL_OWNER_ID, timezone="UTC"))
    await PreferenceRepository(db=db).save(Preference(owner_id=first_account.id, timezone="Europe/Paris"))

    # Half one: the gated raw org read is refused for this caller.
    global_result = await run_query(
        db=db, branch=default_branch, query=GLOBAL_QUERY, account_session=session_first_account
    )
    assert global_result.errors is not None
    assert global_result.data is None or global_result.data.get("InfrahubGlobalPreferences") is None

    # Half two: the same caller still reads the org's value as their inherited layer, no errors.
    effective_result = await run_query(
        db=db, branch=default_branch, query=EFFECTIVE_QUERY, account_session=session_first_account
    )
    assert effective_result.errors is None
    assert effective_result.data is not None
    assert effective_result.data["InfrahubEffectivePreferences"]["timezone"] == {
        "value": "Europe/Paris",
        "source": "USER",
        "inherited": {"value": "UTC", "source": "GLOBAL"},
    }

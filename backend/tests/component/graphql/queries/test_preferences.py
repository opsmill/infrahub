from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.auth.session import AccountSession, AnonymousSession
from infrahub.auth.types import AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

QUERY_EFFECTIVE_PREFERENCES = """
query {
  InfrahubEffectivePreferences {
    date_format
    timezone
  }
}
"""


async def _set_global_preference(db: InfrahubDatabase, date_format: str | None, timezone: str | None) -> Node:
    """Create or update the CoreGlobalPreference singleton with explicit values."""
    existing = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE, limit=1)
    if existing:
        obj = existing[0]
        obj.date_format.value = date_format
        obj.timezone.value = timezone
        await obj.save(db=db)
        return obj

    obj = await Node.init(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
    await obj.new(db=db, date_format=date_format, timezone=timezone)
    await obj.save(db=db)
    return obj


async def _set_user_preference(
    db: InfrahubDatabase, account: Node, date_format: str | None, timezone: str | None
) -> Node:
    """Create or update the CoreUserPreference row of the given account with explicit values."""
    existing = await NodeManager.query(
        db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [account.id]}, limit=1
    )
    if existing:
        obj = existing[0]
        obj.date_format.value = date_format
        obj.timezone.value = timezone
        await obj.save(db=db)
        return obj

    obj = await Node.init(db=db, schema=InfrahubKind.USERPREFERENCE)
    await obj.new(db=db, account=account, date_format=date_format, timezone=timezone)
    await obj.save(db=db)
    return obj


async def _query_effective_preferences(
    db: InfrahubDatabase, branch: Branch, account_session: AccountSession | None
) -> dict | None:
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    result = await graphql(
        schema=gql_params.schema,
        source=QUERY_EFFECTIVE_PREFERENCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    if result.errors:
        raise ExceptionGroup("query failed", [e.original_error or e for e in result.errors])
    assert result.data
    return result.data["InfrahubEffectivePreferences"]


async def test_no_global_and_no_user_preference_returns_nulls(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    default_branch.update_schema_hash()
    response = await _query_effective_preferences(db=db, branch=default_branch, account_session=session_first_account)

    assert response == {"date_format": None, "timezone": None}


@pytest.mark.parametrize(
    "global_values,user_values,expected",
    [
        pytest.param(
            {"date_format": None, "timezone": None},
            None,
            {"date_format": None, "timezone": None},
            id="empty-global-no-user",
        ),
        pytest.param(
            {"date_format": "yyyy-MM-dd", "timezone": "UTC"},
            None,
            {"date_format": "yyyy-MM-dd", "timezone": "UTC"},
            id="global-only",
        ),
        pytest.param(
            {"date_format": "yyyy-MM-dd", "timezone": "UTC"},
            {"date_format": "dd/MM/yyyy", "timezone": "Europe/Paris"},
            {"date_format": "dd/MM/yyyy", "timezone": "Europe/Paris"},
            id="user-overrides-global",
        ),
        pytest.param(
            {"date_format": None, "timezone": "UTC"},
            {"date_format": "relative", "timezone": None},
            {"date_format": "relative", "timezone": "UTC"},
            id="mixed-per-attribute",
        ),
        pytest.param(
            {"date_format": None, "timezone": None},
            {"date_format": None, "timezone": None},
            {"date_format": None, "timezone": None},
            id="both-rows-empty",
        ),
    ],
)
async def test_effective_preferences_merge_matrix(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
    global_values: dict,
    user_values: dict | None,
    expected: dict,
) -> None:
    default_branch.update_schema_hash()
    await _set_global_preference(db=db, **global_values)
    if user_values is not None:
        await _set_user_preference(db=db, account=first_account, **user_values)

    response = await _query_effective_preferences(db=db, branch=default_branch, account_session=session_first_account)

    assert response == expected


async def test_each_account_sees_its_own_effective_view(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    second_account: Node,
    session_first_account: AccountSession,
) -> None:
    default_branch.update_schema_hash()
    await _set_global_preference(db=db, date_format="yyyy-MM-dd", timezone="UTC")
    await _set_user_preference(db=db, account=first_account, date_format="dd/MM/yyyy", timezone=None)

    session_second_account = AccountSession(authenticated=True, account_id=second_account.id, auth_type=AuthType.JWT)

    first_response = await _query_effective_preferences(
        db=db, branch=default_branch, account_session=session_first_account
    )
    second_response = await _query_effective_preferences(
        db=db, branch=default_branch, account_session=session_second_account
    )

    assert first_response == {"date_format": "dd/MM/yyyy", "timezone": "UTC"}
    assert second_response == {"date_format": "yyyy-MM-dd", "timezone": "UTC"}


async def test_effective_preferences_rejected_without_account_session(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=None)

    result = await graphql(
        schema=gql_params.schema,
        source=QUERY_EFFECTIVE_PREFERENCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert any("requires an authenticated account" in str(error) for error in result.errors)


async def test_effective_preferences_rejected_for_anonymous_session(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, account_session=AnonymousSession())

    result = await graphql(
        schema=gql_params.schema,
        source=QUERY_EFFECTIVE_PREFERENCES,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert any("requires an authenticated account" in str(error) for error in result.errors)

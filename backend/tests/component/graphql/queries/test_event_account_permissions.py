from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from infrahub.events.constants import ACCOUNT_EVENT_PREFIX
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

QUERY_ACCOUNT_EVENTS = """
query($event_type: [String!]) {
  InfrahubEvent(event_type: $event_type) {
    count
    edges {
      node {
        id
        event
      }
    }
  }
}
"""

_EMPTY_PREFECT_RESULT = {"count": 0, "edges": []}


async def test_account_event_query_rejected_for_non_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
    )

    result = await graphql(
        schema=gql_params.schema,
        source=QUERY_ACCOUNT_EVENTS,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"event_type": ["infrahub.account.logged_in"]},
    )

    assert result.errors
    assert any("You are not allowed to" in str(e) for e in result.errors)


async def test_account_event_query_allowed_for_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    create_test_admin: Node,
    session_admin: AccountSession,
) -> None:
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_admin,
    )

    with patch(
        "infrahub.graphql.queries.event.PrefectEvent.query",
        AsyncMock(return_value=_EMPTY_PREFECT_RESULT),
    ):
        result = await graphql(
            schema=gql_params.schema,
            source=QUERY_ACCOUNT_EVENTS,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"event_type": ["infrahub.account.logged_in"]},
        )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubEvent"]["count"] == 0


async def test_non_account_event_query_allowed_for_non_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Non-account event types must not trigger the admin check."""
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
    )

    with patch(
        "infrahub.graphql.queries.event.PrefectEvent.query",
        AsyncMock(return_value=_EMPTY_PREFECT_RESULT),
    ):
        result = await graphql(
            schema=gql_params.schema,
            source=QUERY_ACCOUNT_EVENTS,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"event_type": ["infrahub.node.created"]},
        )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubEvent"]["count"] == 0


async def test_no_event_type_filter_excludes_account_events_for_non_admin(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    first_account: Node,
    session_first_account: AccountSession,
) -> None:
    """Without event_type, non-admin queries must exclude account events via exclude_prefix."""
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_first_account,
    )

    mock_query = AsyncMock(return_value=_EMPTY_PREFECT_RESULT)
    with patch("infrahub.graphql.queries.event.PrefectEvent.query", mock_query):
        result = await graphql(
            schema=gql_params.schema,
            source=QUERY_ACCOUNT_EVENTS,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )

    assert result.errors is None
    assert result.data

    event_filter = mock_query.call_args.kwargs["event_filter"]
    assert event_filter.event is not None
    assert event_filter.event.exclude_prefix == [ACCOUNT_EVENT_PREFIX]

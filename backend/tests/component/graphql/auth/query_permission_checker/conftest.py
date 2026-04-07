from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from infrahub.graphql.initialization import GraphqlContext, GraphqlParams
from infrahub.graphql.resolvers.account_metadata import AccountMetadataResolver

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.permissions import PermissionManager


def build_graphql_query_mock(
    *,
    branch_name: str = "main",
    contains_mutation: bool = True,
    operation_names: list[str] | None = None,
) -> MagicMock:
    """Build a MagicMock that behaves like InfrahubGraphQLQueryAnalyzer."""
    from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

    query = MagicMock(spec=InfrahubGraphQLQueryAnalyzer)
    query.branch = MagicMock()
    query.branch.name = branch_name
    query.contains_mutation = contains_mutation
    query.operation_names = operation_names or []
    return query


def build_query_params(
    session: AccountSession,
    permission_manager: PermissionManager,
) -> GraphqlParams:
    """Build GraphqlParams with a fully constructed (non-mock) GraphqlContext."""
    graphql_context = GraphqlContext(
        db=MagicMock(),
        branch=MagicMock(),
        types=MagicMock(),
        single_relationship_resolver=MagicMock(),
        many_relationship_resolver=MagicMock(),
        account_metadata_resolver=AccountMetadataResolver(),
        account_session=session,
        permissions=permission_manager,
    )
    return GraphqlParams(schema=MagicMock(), context=graphql_context)

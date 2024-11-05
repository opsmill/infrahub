from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphql import ExecutionResult, graphql

from infrahub.core.branch import Branch
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices, services

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.database import InfrahubDatabase


async def graphql_mutation(
    query: str,
    db: InfrahubDatabase,
    branch: Branch | None = None,
    variables: dict[str, Any] | None = None,
    service: InfrahubServices | None = None,
    account_session: AccountSession | None = None,
) -> ExecutionResult:
    branch = branch or await Branch.get_by_name(name="main", db=db)
    service = service or services.service
    variables = variables or {}
    gql_params = prepare_graphql_params(
        db=db,
        include_subscription=False,
        include_mutation=True,
        branch=branch,
        service=service,
        account_session=account_session,
    )
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


async def graphql_query(
    query: str,
    db: InfrahubDatabase,
    branch: Branch,
    variables: dict[str, Any] | None = None,
    service: InfrahubServices | None = None,
) -> ExecutionResult:
    service = service or services.service

    variables = variables or {}
    gql_params = prepare_graphql_params(
        db=db, include_subscription=False, include_mutation=False, branch=branch, service=service
    )
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )

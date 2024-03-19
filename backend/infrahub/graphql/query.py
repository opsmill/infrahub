from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.graphql import prepare_graphql_params

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult

    from infrahub.database import InfrahubDatabase


async def execute_query(
    name: str,
    db: InfrahubDatabase,
    params: Optional[dict] = None,
    branch: Union[Branch, str] = None,
    at: Union[Timestamp, str] = None,
) -> ExecutionResult:
    """Helper function to Execute a GraphQL Query."""

    if not isinstance(branch, Branch):
        branch = await registry.get_branch(db=db, branch=branch)
    at = Timestamp(at)

    graphql_query = await NodeManager.get_one_by_default_filter(
        db=db, id=name, schema_name=InfrahubKind.GRAPHQLQUERY, branch=branch, at=at
    )
    if not graphql_query:
        raise ValueError(f"Unable to find the {InfrahubKind.GRAPHQLQUERY} {name}")

    gql_params = prepare_graphql_params(branch=branch, db=db, at=at, include_mutation=False, include_subscription=False)

    result = await graphql(
        schema=gql_params.schema,
        source=graphql_query.query.value,
        context_value=gql_params.context,
        root_value=None,
        variable_values=params or {},
    )

    return result

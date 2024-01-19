from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

import graphene
from graphql import graphql

from infrahub.core import get_branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp

from .generator import generate_query_mixin
from .schema import InfrahubBaseQuery

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def execute_query(
    name: str,
    db: InfrahubDatabase,
    params: Optional[dict] = None,
    branch: Union[Branch, str] = None,
    at: Union[Timestamp, str] = None,
) -> ExecutionResult:
    """Helper function to Execute a GraphQL Query."""

    branch = branch or await get_branch(db=db, branch=branch)
    at = Timestamp(at)

    graphql_query = await NodeManager.get_one_by_default_filter(
        db=db, id=name, schema_name=InfrahubKind.GRAPHQLQUERY, branch=branch, at=at
    )
    if not graphql_query:
        raise ValueError(f"Unable to find the {InfrahubKind.GRAPHQLQUERY} {name}")

    result = await graphql(
        graphene.Schema(query=await get_gql_query(db=db, branch=branch), auto_camelcase=False).graphql_schema,
        source=graphql_query.query.value,
        context_value={
            "infrahub_database": db,
            "infrahub_branch": branch,
            "infrahub_at": at,
            "related_node_ids": set(),
        },
        root_value=None,
        variable_values=params or {},
    )

    return result


async def get_gql_query(db: InfrahubDatabase, branch: Union[Branch, str]) -> type[InfrahubBaseQuery]:
    QueryMixin = await generate_query_mixin(db=db, branch=branch)

    class Query(InfrahubBaseQuery, QueryMixin):
        pass

    return Query

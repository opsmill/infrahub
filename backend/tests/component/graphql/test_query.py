from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from graphql import graphql

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreGraphQLQuery
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params

if TYPE_CHECKING:
    from graphql.execution import ExecutionResult

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def execute_query(
    name: str,
    db: InfrahubDatabase,
    params: dict | None = None,
    branch: Branch | str | None = None,
    at: Timestamp | str | None = None,
) -> ExecutionResult:
    """Helper function to Execute a GraphQL Query."""

    if not isinstance(branch, Branch):
        branch = await registry.get_branch(db=db, branch=branch)
    at = Timestamp(at)

    graphql_query = await NodeManager.get_one_by_default_filter(
        db=db, id=name, kind=CoreGraphQLQuery, branch=branch, at=at
    )
    if not graphql_query:
        raise ValueError(f"Unable to find the {InfrahubKind.GRAPHQLQUERY} {name}")

    gql_params = await prepare_graphql_params(
        branch=branch,
        db=db,
        at=at,
    )

    result = await graphql(
        schema=gql_params.schema,
        source=graphql_query.query.value,
        context_value=gql_params.context,
        root_value=None,
        variable_values=params or {},
    )

    return result


async def test_execute_query(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)

    t2 = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await t2.new(db=db, name="Red", description="The Red tag")
    await t2.save(db=db)

    q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await q1.new(db=db, name="query01", query="query { BuiltinTag { count }}")
    await q1.save(db=db)

    default_branch.update_schema_hash()
    result = await execute_query(name="query01", db=db, branch=default_branch)

    assert result.errors is None
    assert result.data == {"BuiltinTag": {"count": 2}}


async def test_execute_missing_query(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    default_branch.update_schema_hash()
    with pytest.raises(ValueError) as exc:
        await execute_query(name="query02", db=db, branch=default_branch)

    assert "Unable to find the CoreGraphQLQuery" in str(exc.value)

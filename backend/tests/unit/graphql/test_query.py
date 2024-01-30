import pytest

from infrahub.core.branch.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.graphql.query import execute_query


async def test_execute_query(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    t1 = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await t1.new(db=db, name="Blue", description="The Blue tag")
    await t1.save(db=db)

    t2 = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await t2.new(db=db, name="Red", description="The Red tag")
    await t2.save(db=db)

    q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await q1.new(db=db, name="query01", query="query { BuiltinTag { count }}")
    await q1.save(db=db)

    result = await execute_query(name="query01", db=db, branch=default_branch)

    assert result.errors is None
    assert result.data == {"BuiltinTag": {"count": 2}}


async def test_execute_missing_query(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    with pytest.raises(ValueError) as exc:
        await execute_query(name="query02", db=db, branch=default_branch)

    assert "Unable to find the CoreGraphQLQuery" in str(exc.value)

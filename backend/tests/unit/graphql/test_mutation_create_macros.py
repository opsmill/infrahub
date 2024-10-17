from __future__ import annotations

from typing import TYPE_CHECKING

from graphql import graphql

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.schema import CHILD, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_create_related_macro(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    await load_schema(db, schema=SchemaRoot(nodes=[CHILD, THING]))
    fred = await Node.init(schema=TestKind.CHILD, db=db)
    await fred.new(db=db, name="Fred", height=110)
    await fred.save(db=db)

    query = """
    mutation {
        TestingThingCreate(data: {
            name: { value: "Ball" },
            color: { value: "red" },
            owner: { id: "Fred" }
        }
        ) {
            ok
            object {
                id
                name { value }
                description { value }
            }
        }
    }
    """
    gql_params = prepare_graphql_params(db=db, include_subscription=False, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestingThingCreate"]["ok"] is True
    assert result.data["TestingThingCreate"]["object"]["description"]["value"] == "Fred's red Ball"

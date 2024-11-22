from __future__ import annotations

from typing import TYPE_CHECKING

from graphql import graphql

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.schema import CHILD, LOCATION_SCHEMA, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_create_with_jinja2_computed_attributes_on_related_node(
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


async def test_create_with_jinja2_computed_attributes_on_hierarchial_node(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> None:
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    await load_schema(db, schema=LOCATION_SCHEMA)

    continent = await Node.init(schema=TestKind.CONTINENT, db=db)
    await continent.new(db=db, name="Europe", shortname="eu")
    await continent.save(db=db)

    country = await Node.init(schema=TestKind.COUNTRY, db=db)
    await country.new(db=db, name="Sweden", shortname="se", parent=continent)
    await country.save(db=db)

    query = """
    mutation TestingSiteCreate($parent: String!) {
        TestingSiteCreate(data: {
            name: { value: "Stockholm" },
            shortname: { value: "sth" },
            parent: { id: $parent },
        }
        ) {
            ok
            object {
                id
                name { value }
                slug { value }
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
        variable_values={"parent": country.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestingSiteCreate"]["ok"] is True
    assert result.data["TestingSiteCreate"]["object"]["slug"]["value"] == "eu-se-sth"

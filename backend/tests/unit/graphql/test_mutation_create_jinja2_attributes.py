from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.graphql.initialization import prepare_graphql_params
from tests.constants import TestKind
from tests.helpers.graphql import graphql
from tests.helpers.schema import CHILD, LOCATION_SCHEMA, THING, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_create_with_jinja2_computed_attributes_on_related_node(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None, branch: Branch
) -> None:
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=branch.name)
    branch.update_schema_hash()
    await branch.save(db=db)
    await load_schema(db, branch_name=branch.name, schema=SchemaRoot(nodes=[CHILD, THING]))

    fred = await Node.init(schema=TestKind.CHILD, db=db, branch=branch)
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
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None, branch: Branch
) -> None:
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=branch.name)
    branch.update_schema_hash()
    await branch.save(db=db)
    await load_schema(db, branch_name=branch.name, schema=LOCATION_SCHEMA)

    continent = await Node.init(schema=TestKind.CONTINENT, db=db, branch=branch)
    await continent.new(db=db, name="Europe", shortname="eu")
    await continent.save(db=db)

    country = await Node.init(schema=TestKind.COUNTRY, db=db, branch=branch)
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
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
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


async def test_create_with_jinja2_with_generics(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None, branch: Branch
) -> None:
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=branch.name)
    branch.update_schema_hash()
    await branch.save(db=db)
    await load_schema(db, branch_name=branch.name, schema=LOCATION_SCHEMA)

    continent_query = """
    mutation TestingContinentCreate {
        TestingContinentCreate(data: {
            name: { value: "Europe" },
            shortname: { value: "eu" },
        }
        ) {
            ok
            object {
                id
                name { value }
                code { value }
            }
        }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    continent_result = await graphql(
        schema=gql_params.schema,
        source=continent_query,
        context_value=gql_params.context,
        root_value=None,
    )

    assert continent_result.errors is None
    assert continent_result.data
    assert continent_result.data["TestingContinentCreate"]["ok"] is True
    assert continent_result.data["TestingContinentCreate"]["object"]["code"]["value"] == "eu"
    assert continent_result.data["TestingContinentCreate"]["object"]["id"]
    continent_id = continent_result.data["TestingContinentCreate"]["object"]["id"]

    country_query = """
    mutation TestingCountryCreate($parent: String!) {
        TestingCountryCreate(data: {
            name: { value: "Sweden" },
            shortname: { value: "se" },
            parent: { id: $parent },
        }
        ) {
            ok
            object {
                id
                name { value }
                code { value }
            }
        }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    country_result = await graphql(
        schema=gql_params.schema,
        source=country_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"parent": continent_id},
    )

    assert country_result.errors is None
    assert country_result.data
    assert country_result.data["TestingCountryCreate"]["ok"] is True
    # The country code is different and with three letters because the generic computed attribute
    # is overriden on the country
    assert country_result.data["TestingCountryCreate"]["object"]["code"]["value"] == "swe"
    assert country_result.data["TestingCountryCreate"]["object"]["id"]
    country_id = country_result.data["TestingCountryCreate"]["object"]["id"]

    site_query = """
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
                code { value }
            }
        }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    site_result = await graphql(
        schema=gql_params.schema,
        source=site_query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"parent": country_id},
    )

    assert site_result.errors is None
    assert site_result.data
    assert site_result.data["TestingSiteCreate"]["ok"] is True
    assert site_result.data["TestingSiteCreate"]["object"]["code"]["value"] == "st"

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import ComputedAttributeKind
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot, internal_schema
from infrahub.core.schema.computed_attribute import ComputedAttribute
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


async def test_create_with_jinja2_format_filter_on_number_pool(
    db: InfrahubDatabase,
    default_branch: Branch,
    node_group_schema: None,
    data_schema: None,
    register_core_models_schema: None,
    branch: Branch,
) -> None:
    """Test that Jinja2 computed attributes using format filter on NumberPool values work correctly.

    This is a regression test for GitHub issue #7836 where using the format filter
    (e.g., "{{ '%09d' | format(number__value) }}") on a NumberPool attribute would fail
    with "%d format: a real number is required, not NoneType" because the preview object
    created during node creation had process_pools=False, leaving the pool value as None.
    """
    from infrahub.core.constants import InfrahubKind
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool

    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema, branch=branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    branch.update_schema_hash()
    await branch.save(db=db)

    # Schema with NumberPool attribute and Jinja2 computed attribute using format filter
    ticket_schema = NodeSchema(
        name="Ticket",
        namespace="Testing",
        attributes=[
            AttributeSchema(name="title", kind="Text", optional=False),
            AttributeSchema(name="sequence_number", kind="NumberPool", optional=False, read_only=True, unique=True),
            AttributeSchema(
                name="serial_number",
                kind="Text",
                optional=False,
                read_only=True,
                computed_attribute=ComputedAttribute(
                    kind=ComputedAttributeKind.JINJA2,
                    jinja2_template="TKT{{ '%09d' | format(sequence_number__value) }}",
                ),
            ),
        ],
    )

    await load_schema(db, branch_name=branch.name, schema=SchemaRoot(nodes=[ticket_schema]))

    query = """
    mutation {
        TestingTicketCreate(data: {
            title: { value: "Test Ticket" }
        }) {
            ok
            object {
                id
                title { value }
                sequence_number { value }
                serial_number { value }
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
    assert result.data["TestingTicketCreate"]["ok"] is True
    # The sequence_number should be allocated from the pool (starting at 1)
    assert result.data["TestingTicketCreate"]["object"]["sequence_number"]["value"] == 1
    # The serial_number should be formatted with leading zeros
    assert result.data["TestingTicketCreate"]["object"]["serial_number"]["value"] == "TKT000000001"

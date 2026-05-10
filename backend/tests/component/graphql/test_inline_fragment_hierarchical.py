from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.computed_attribute.models import ComputedAttrJinja2GraphQL
from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.display_labels.models import DisplayLabelJinja2GraphQL
from infrahub.hfid.models import HFIDGraphQL
from tests.helpers.graphql import graphql_query
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


# ---------------------------------------------------------------------------
# Schema matching issue: country_code only exists on Country, not on
# the LocationGeneric hierarchy generic.  City's computed location_code
# references parent__country_code__value which must produce an inline
# fragment in the generated GraphQL query.
# ---------------------------------------------------------------------------

LOCATION_GENERIC = GenericSchema(
    name="Location",
    namespace="Testing",
    hierarchical=True,
    label="Location",
    default_filter="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True, optional=False),
        AttributeSchema(name="shortname", kind="Text", unique=True, optional=False),
    ],
)

CONTINENT = NodeSchema(
    name="Continent",
    namespace="Testing",
    label="Continent",
    default_filter="name__value",
    inherit_from=["TestingLocation"],
    parent="",
    children="TestingCountry",
    generate_profile=False,
)

COUNTRY = NodeSchema(
    name="Country",
    namespace="Testing",
    label="Country",
    default_filter="name__value",
    inherit_from=["TestingLocation"],
    parent="TestingContinent",
    children="TestingCity",
    generate_profile=False,
    attributes=[
        AttributeSchema(name="country_code", kind="Text", optional=False),
        AttributeSchema(
            name="country_path",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ parent__name__value }}-{{ shortname__value }}",
            ),
        ),
    ],
)

CITY = NodeSchema(
    name="City",
    namespace="Testing",
    label="City",
    default_filter="name__value",
    inherit_from=["TestingLocation"],
    parent="TestingCountry",
    children="",
    generate_profile=False,
    attributes=[
        AttributeSchema(
            name="location_code",
            kind="Text",
            optional=False,
            read_only=True,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2,
                jinja2_template="{{ parent__country_code__value }}-{{ shortname__value }}",
            ),
        ),
    ],
)


async def assert_correct_graphql_structure(
    db: InfrahubDatabase, default_branch: Branch, rendered_query: str, expected_value: str
) -> None:
    assert "... on TestingCountry" in rendered_query

    result = await graphql_query(query=rendered_query, db=db, branch=default_branch)

    assert result.errors is None
    edges = result.data["TestingCity"]["edges"]
    assert len(edges) == 1

    node = edges[0]["node"]
    assert node["parent"]["node"]["country_code"]["value"] == expected_value


@pytest.fixture
async def hierarchical_schema(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> SchemaBranch:
    await load_schema(
        db,
        schema=SchemaRoot(generics=[LOCATION_GENERIC], nodes=[CONTINENT, COUNTRY, CITY]),
    )
    return registry.schema.get_schema_branch(name=default_branch.name)


def _extract_variables(template: str) -> list[str]:
    return InfrahubJinja2Template(template=template).get_variables()


async def test_computed_attr_graphql_query_executes_successfully(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_schema: SchemaBranch,
) -> None:
    """The GraphQL query generated for a computed attribute that references a
    peer-only parent attribute must use an inline fragment and execute without
    errors against the database.
    """
    continent = await Node.init(db=db, schema="TestingContinent", branch=default_branch)
    await continent.new(db=db, name="Europe", shortname="eu")
    await continent.save(db=db)

    country = await Node.init(db=db, schema="TestingCountry", branch=default_branch)
    expected_country_code = "SWE"
    await country.new(db=db, name="Sweden", shortname="se", country_code=expected_country_code, parent=continent)
    await country.save(db=db)

    city = await Node.init(db=db, schema="TestingCity", branch=default_branch)
    await city.new(db=db, name="Stockholm", shortname="sth", parent=country)
    await city.save(db=db)

    city_schema = hierarchical_schema.get_node(name="TestingCity")
    attr_schema = city_schema.get_attribute(name="location_code")
    variables = _extract_variables(attr_schema.computed_attribute.jinja2_template)

    graphql_obj = ComputedAttrJinja2GraphQL(
        node_schema=city_schema,
        attribute_schema=attr_schema,
        variables=variables,
    )

    rendered_query = graphql_obj.render_graphql_query(query_filter="parent__ids", filter_id=country.id)
    await assert_correct_graphql_structure(db, default_branch, rendered_query, expected_country_code)


async def test_display_label_graphql_query_executes_successfully(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_schema: SchemaBranch,
) -> None:
    """The GraphQL query generated for a display label that references a
    peer-only parent attribute must use an inline fragment and execute without errors.
    """
    continent = await Node.init(db=db, schema="TestingContinent", branch=default_branch)
    await continent.new(db=db, name="Asia", shortname="as")
    await continent.save(db=db)

    country = await Node.init(db=db, schema="TestingCountry", branch=default_branch)
    expected_country_code = "JPN"
    await country.new(db=db, name="Japan", shortname="jp", country_code=expected_country_code, parent=continent)
    await country.save(db=db)

    city = await Node.init(db=db, schema="TestingCity", branch=default_branch)
    await city.new(db=db, name="Tokyo", shortname="tky", parent=country)
    await city.save(db=db)

    city_schema = hierarchical_schema.get_node(name="TestingCity")

    graphql_obj = DisplayLabelJinja2GraphQL(
        filter_key="ids",
        node_schema=city_schema,
        variables=["parent__country_code__value", "shortname__value"],
    )

    rendered_query = graphql_obj.render_graphql_query(filter_id=city.id)
    await assert_correct_graphql_structure(db, default_branch, rendered_query, expected_country_code)


async def test_hfid_graphql_query_executes_successfully(
    db: InfrahubDatabase,
    default_branch: Branch,
    hierarchical_schema: SchemaBranch,
) -> None:
    """The GraphQL query generated for an HFID that references a peer-only
    parent attribute must use an inline fragment and execute without errors.
    """
    continent = await Node.init(db=db, schema="TestingContinent", branch=default_branch)
    await continent.new(db=db, name="Africa", shortname="af")
    await continent.save(db=db)

    country = await Node.init(db=db, schema="TestingCountry", branch=default_branch)
    expected_country_code = "KEN"

    await country.new(db=db, name="Kenya", shortname="ke", country_code=expected_country_code, parent=continent)
    await country.save(db=db)

    city = await Node.init(db=db, schema="TestingCity", branch=default_branch)
    await city.new(db=db, name="Nairobi", shortname="nbi", parent=country)
    await city.save(db=db)

    city_schema = hierarchical_schema.get_node(name="TestingCity")

    graphql_obj = HFIDGraphQL(
        filter_key="ids",
        node_schema=city_schema,
        variables=["parent__country_code__value", "shortname__value"],
    )

    rendered_query = graphql_obj.render_graphql_query(filter_id=city.id)
    await assert_correct_graphql_structure(db, default_branch, rendered_query, expected_country_code)

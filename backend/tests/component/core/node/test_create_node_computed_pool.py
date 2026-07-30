from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.graphql.registry import registry as graphql_registry
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.graphql import graphql
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_TASK
from tests.helpers.schema_builders import computed_jinja2_attr

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import AttributeSchema
    from infrahub.database import InfrahubDatabase


def _snow_schema_with_format_identifier(
    identifier_template: str = "INC{{ '%09d' | format(number__value) }}",
    extra_incident_attrs: list[AttributeSchema] | None = None,
) -> SchemaRoot:
    """Snow schema whose incident identifier formats the pool value with a leading-zero filter."""
    task = copy.deepcopy(SNOW_TASK)
    task.get_attribute(name="number").parameters = NumberPoolParameters(start_range=1, end_range=1000)
    incident = copy.deepcopy(SNOW_INCIDENT)
    incident.get_attribute(name="identifier").computed_attribute.jinja2_template = identifier_template
    if extra_incident_attrs:
        incident.attributes.extend(extra_incident_attrs)
    return SchemaRoot(generics=[task], nodes=[incident])


async def _register_and_provision_pools(db: InfrahubDatabase, branch: Branch, schema: SchemaRoot) -> None:
    registry.schema.register_schema(schema=schema, branch=branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema)
    synchronizer = SchemaNumberPoolSynchronizer(db=db, schema_manager=registry.schema, upserter=upserter)
    await synchronizer.run()


async def test_create_with_jinja2_format_filter_on_number_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """A Jinja2 macro that formats a pool-sourced attribute renders once the pool is allocated."""
    await _register_and_provision_pools(db=db, branch=default_branch, schema=_snow_schema_with_format_identifier())

    incident_schema = registry.schema.get_node_schema(name="SnowIncident", branch=default_branch)
    incident = await create_node(
        data={"title": "The first issue"},
        db=db,
        branch=default_branch,
        schema=incident_schema,
    )

    assert incident.number.value == 1
    assert incident.identifier.value == "INC000000001"


async def test_new_with_unallocated_pool_renders_independent_macros(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """With pools unallocated, a pool-dependent macro is skipped while other macros still render."""
    schema = _snow_schema_with_format_identifier(
        extra_incident_attrs=[computed_jinja2_attr(name="slug", template="{{ title__value | lower }}", unique=False)]
    )
    await _register_and_provision_pools(db=db, branch=default_branch, schema=schema)

    incident_schema = registry.schema.get_node_schema(name="SnowIncident", branch=default_branch)
    node = await Node.init(db=db, schema=incident_schema, branch=default_branch)
    await node.new(db=db, process_pools=False, title="First Issue")

    assert node.number.value is None
    assert node.slug.value == "first issue"


async def test_create_via_graphql_with_jinja2_format_filter_on_number_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """Creating the node through the GraphQL API renders the pool-formatted computed attribute."""
    await _register_and_provision_pools(db=db, branch=default_branch, schema=_snow_schema_with_format_identifier())
    default_branch.update_schema_hash()
    graphql_registry.clear_cache()

    query = """
    mutation {
        SnowIncidentCreate(data: { title: { value: "The first issue" } }) {
            ok
            object {
                id
                identifier { value }
            }
        }
    }
    """
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None
    assert result.data
    assert result.data["SnowIncidentCreate"]["ok"] is True
    assert result.data["SnowIncidentCreate"]["object"]["identifier"]["value"] == "INC000000001"


async def test_create_with_jinja2_macro_mixing_pool_and_plain_attributes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """A macro referencing both a pool value and a plain attribute renders every variable after allocation."""
    schema = _snow_schema_with_format_identifier(
        identifier_template="INC{{ '%09d' | format(number__value) }}-{{ title__value | lower }}"
    )
    await _register_and_provision_pools(db=db, branch=default_branch, schema=schema)

    incident_schema = registry.schema.get_node_schema(name="SnowIncident", branch=default_branch)
    incident = await create_node(
        data={"title": "First Issue"},
        db=db,
        branch=default_branch,
        schema=incident_schema,
    )

    assert incident.number.value == 1
    assert incident.identifier.value == "INC000000001-first issue"

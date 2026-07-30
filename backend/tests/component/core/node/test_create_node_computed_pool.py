from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from tests.helpers.number_pool import register_and_provision_number_pools, snow_schema_with_format_identifier
from tests.helpers.schema_builders import computed_jinja2_attr

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_create_with_jinja2_format_filter_on_number_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """A Jinja2 macro that formats a pool-sourced attribute renders once the pool is allocated."""
    await register_and_provision_number_pools(db=db, branch=default_branch, schema=snow_schema_with_format_identifier())

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
    schema = snow_schema_with_format_identifier(
        extra_incident_attrs=[computed_jinja2_attr(name="slug", template="{{ title__value | lower }}", unique=False)]
    )
    await register_and_provision_number_pools(db=db, branch=default_branch, schema=schema)

    incident_schema = registry.schema.get_node_schema(name="SnowIncident", branch=default_branch)
    node = await Node.init(db=db, schema=incident_schema, branch=default_branch)
    await node.new(db=db, process_pools=False, title="First Issue")

    assert node.number.value is None
    assert node.slug.value == "first issue"


async def test_create_with_jinja2_macro_mixing_pool_and_plain_attributes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """A macro referencing both a pool value and a plain attribute renders every variable after allocation."""
    schema = snow_schema_with_format_identifier(
        identifier_template="INC{{ '%09d' | format(number__value) }}-{{ title__value | lower }}"
    )
    await register_and_provision_number_pools(db=db, branch=default_branch, schema=schema)

    incident_schema = registry.schema.get_node_schema(name="SnowIncident", branch=default_branch)
    incident = await create_node(
        data={"title": "First Issue"},
        db=db,
        branch=default_branch,
        schema=incident_schema,
    )

    assert incident.number.value == 1
    assert incident.identifier.value == "INC000000001-first issue"


async def test_create_with_chained_macro_depending_on_pool_macro(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None
) -> None:
    """A computed attribute chained on a pool-dependent one renders once the pool is allocated."""
    schema = snow_schema_with_format_identifier(
        extra_incident_attrs=[
            computed_jinja2_attr(name="reference", template="REF-{{ identifier__value }}", unique=False)
        ]
    )
    await register_and_provision_number_pools(db=db, branch=default_branch, schema=schema)

    incident_schema = registry.schema.get_node_schema(name="SnowIncident", branch=default_branch)
    incident = await create_node(
        data={"title": "First Issue"},
        db=db,
        branch=default_branch,
        schema=incident_schema,
    )

    assert incident.number.value == 1
    assert incident.identifier.value == "INC000000001"
    assert incident.reference.value == "REF-INC000000001"

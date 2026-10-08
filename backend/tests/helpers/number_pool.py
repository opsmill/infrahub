from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    ComputedAttributeKind,
    InfrahubKind,
    RelationshipCardinality,
)
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters, NumberPoolParameters
from infrahub.core.schema.attribute_schema import NumberAttributeSchema
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_shorthand import NumberPoolShorthandMirror
from infrahub.pools.number_pool_space import SchemaAttributeDomains
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from infrahub.schema.tasks import schema_updated
from tests.helpers.schema import TICKET
from tests.helpers.schema.snow import SNOW_INCIDENT, SNOW_TASK

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


def snow_schema_with_format_identifier(
    identifier_template: str = "INC{{ '%09d' | format(number__value) }}",
    extra_incident_attrs: list[AttributeSchema] | None = None,
) -> SchemaRoot:
    """Snow schema whose incident identifier formats the pool value with a leading-zero filter."""
    task = copy.deepcopy(SNOW_TASK)
    task.get_attribute(name="number").parameters = NumberPoolParameters(start_range=1, end_range=1000)
    incident = copy.deepcopy(SNOW_INCIDENT)
    incident.get_attribute(name="identifier").computed_attribute = ComputedAttribute(
        kind=ComputedAttributeKind.JINJA2, jinja2_template=identifier_template
    )
    if extra_incident_attrs:
        incident.attributes.extend(extra_incident_attrs)
    return SchemaRoot(generics=[task], nodes=[incident])


async def register_and_provision_number_pools(db: InfrahubDatabase, branch: Branch, schema: SchemaRoot) -> None:
    """Register the schema and provision the number pools defined by its NumberPool attributes."""
    registry.schema.register_schema(schema=schema, branch=branch.name)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
    upserter = SchemaNumberPoolUpserter(db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository)
    synchronizer = SchemaNumberPoolSynchronizer(
        db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
    )
    await synchronizer.run()


async def run_schema_updated_workflow(service: InfrahubServices, branch: Branch) -> None:
    """Run the workflow a schema update triggers, which provisions and reconciles the schema-created number pools."""
    # Integration tests install no event trigger, so the flow the schema-updated trigger starts is called directly.
    context = InfrahubContext.init(
        branch=branch, account=AccountSession(account_id=SYSTEM_USER_ID, auth_type=AuthType.NONE)
    )
    await schema_updated(
        branch_name=branch.name,
        schema_hash=registry.schema.get_schema_branch(name=branch.name).get_hash(),
        context=context.to_event_context(),
        service=service,
    )


def shorthand_mirror(db: InfrahubDatabase) -> NumberPoolShorthandMirror:
    return NumberPoolShorthandMirror(repository=NumberPoolRepository(db=db))


async def add_pool_range(db: InfrahubDatabase, pool: Node, start: int, end: int, weight: int | None = None) -> Node:
    pool_range = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOLRANGE)
    await pool_range.new(db=db, start=start, end=end, allocation_weight=weight, pool=pool.get_id())
    await pool_range.save(db=db)
    return pool_range


async def _whole_space(repository: NumberPoolRepository, pool: CoreNumberPool) -> EffectiveSpace:
    """Return the pool's ranges as one unclipped space."""
    return EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=pool.get_id()), domain=NumberDomain())


async def pool_used_numbers(db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch) -> list[int]:
    """Return the numbers the pool accounts for across its ranges."""
    repository = NumberPoolRepository(db=db)
    space = await _whole_space(repository=repository, pool=pool)
    return await repository.get_used(pool=pool, branch=branch, space=space)


async def pool_lowest_free_number(db: InfrahubDatabase, pool: CoreNumberPool, branch: Branch) -> int | None:
    """Return the first number, in allocation order, the pool does not account for, or None when none is left."""
    repository = NumberPoolRepository(db=db)
    space = await _whole_space(repository=repository, pool=pool)
    for segment in space.segments:
        free = await repository.get_free(pool=pool, branch=branch, min_value=segment.start, max_value=segment.end)
        if free is not None:
            return free
    return None


async def create_ticket(db: InfrahubDatabase, kind: str, pool: CoreNumberPool, title: str = "ticket") -> int:
    ticket = await Node.init(db=db, schema=kind)
    await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool.id}})
    await ticket.save(db=db)
    value = ticket.get_attribute("ticket_id").value
    assert isinstance(value, int)
    return value


async def create_range_only_pool(db: InfrahubDatabase, kind: str = TICKET.kind) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name="ranged", node=kind, node_attribute="ticket_id")
    await pool.save(db=db)
    return pool


def ticket_schema_with_parameters(parameters: NumberAttributeParameters) -> NodeSchema:
    return NodeSchema(
        name="Ticket",
        namespace="Testing",
        include_in_menu=True,
        label="Ticket",
        human_friendly_id=["title__value", "ticket_id__value"],
        attributes=[
            AttributeSchema(name="title", kind="Text", optional=False),
            NumberAttributeSchema(name="ticket_id", kind="Number", optional=True, unique=True, parameters=parameters),
        ],
    )


def schema_domains(db: InfrahubDatabase, branch: Branch) -> SchemaAttributeDomains:
    return SchemaAttributeDomains(schema=db.schema, branch=branch)


SCOPED_SITE = NodeSchema(
    name="Site",
    namespace="Scope",
    label="Site",
    human_friendly_id=["name__value"],
    display_label="{{ name__value }}",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

# The pooled number is not unique: a uniqueness constraint would make every value taken kind-wide and
# hide whether a pool keeps the same number apart across scopes.
SCOPED_DEVICE = NodeSchema(
    name="Device",
    namespace="Scope",
    label="Device",
    human_friendly_id=["name__value"],
    display_label="{{ name__value }}",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="number", kind="Number", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="site",
            peer="ScopeSite",
            identifier="scope_device__site",
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)

SCOPED_POOL_SCHEMA = SchemaRoot(nodes=[SCOPED_SITE, SCOPED_DEVICE])

from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema, NumberAttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.queries.resource_manager import resolve_number_pool_utilization
from tests.helpers.schema import TICKET, load_schema


async def test_allocate_from_number_pool(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)

    ticket1 = await Node.init(db=db, schema=TICKET.kind)
    await ticket1.new(db=db, title="ticket1", ticket_id={"from_pool": {"id": np1.id}})
    await ticket1.save(db=db)

    ticket2 = await Node.init(db=db, schema=TICKET.kind)
    await ticket2.new(db=db, title="ticket2", ticket_id={"from_pool": {"id": np1.id}})
    await ticket2.save(db=db)

    assert ticket1.ticket_id.value == 1
    assert ticket2.ticket_id.value == 2

    # If a resource is deleted the allocated number should be returned to the pool
    await ticket1.delete(db=db)

    # Check pool status
    assert await np1.get_free(db=db, branch=default_branch) == [1]

    recreated_ticket1 = await Node.init(db=db, schema=TICKET.kind)
    await recreated_ticket1.new(db=db, title="ticket1", ticket_id={"from_pool": {"id": np1.id}})
    await recreated_ticket1.save(db=db)
    assert recreated_ticket1.ticket_id.value == 1

    # Validate methods at the pool level
    assert await np1.get_used(db=db, branch=default_branch) == [1, 2]

    assert await np1.get_free(db=db, branch=default_branch) == [3]


async def test_resource_utilization(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    """
    Allocates:
    - 1 ticket in first number pool
    - 2 tickets in second number pool
    and verifies resource pool utilization.
    """

    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)

    ticket1_np1 = await Node.init(db=db, schema=TICKET.kind)
    await ticket1_np1.new(db=db, title="ticket1_np1", ticket_id={"from_pool": {"id": np1.id}})
    await ticket1_np1.save(db=db)

    np2 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np2.new(db=db, name="pool2", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np2.save(db=db)

    ticket1_np2 = await Node.init(db=db, schema=TICKET.kind)
    await ticket1_np2.new(db=db, title="ticket1_np2", ticket_id={"from_pool": {"id": np2.id}})
    await ticket1_np2.save(db=db)

    ticket2_np2 = await Node.init(db=db, schema=TICKET.kind)
    await ticket2_np2.new(db=db, title="ticket2_np2", ticket_id={"from_pool": {"id": np2.id}})
    await ticket2_np2.save(db=db)

    utilization_np1 = await resolve_number_pool_utilization(db=db, pool=np1, at=Timestamp(), branch=default_branch)

    assert utilization_np1 == {
        "count": 1,
        "utilization": 10,
        "utilization_default_branch": 10,
        "utilization_branches": 0,
        "edges": [
            {
                "node": {
                    "id": np1.get_id(),
                    "kind": "CoreNumberPool",
                    "display_label": "pool1",
                    "weight": 1,
                    "utilization": 10,
                    "utilization_default_branch": 10,
                    "utilization_branches": 0,
                }
            }
        ],
    }

    utilization_np2 = await resolve_number_pool_utilization(db=db, pool=np2, at=Timestamp(), branch=default_branch)

    assert utilization_np2 == {
        "count": 1,
        "utilization": 20,
        "utilization_default_branch": 20,
        "utilization_branches": 0,
        "edges": [
            {
                "node": {
                    "id": np2.get_id(),
                    "kind": "CoreNumberPool",
                    "display_label": "pool2",
                    "weight": 1,
                    "utilization": 20,
                    "utilization_default_branch": 20,
                    "utilization_branches": 0,
                }
            }
        ],
    }


async def test_allocate_from_number_pool_for_generic(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema
):
    ticket = GenericSchema(
        name="Ticket",
        namespace="Testing",
        include_in_menu=True,
        label="Ticket",
        human_friendly_id=["title__value", "ticket_id__value"],
        default_filter="title__value",
        attributes=[
            AttributeSchema(name="title", kind="Text", optional=False),
            AttributeSchema(name="description", kind="TextArea", optional=True),
            AttributeSchema(name="ticket_id", kind="Number", optional=True, unique=True),
        ],
    )
    speeding_ticket = NodeSchema(
        name="SpeedingTicket",
        namespace="Testing",
        include_in_menu=True,
        label="Speeding Ticket",
        inherit_from=[TICKET.kind],
    )
    parking_ticket = NodeSchema(
        name="ParkingTicket",
        namespace="Testing",
        include_in_menu=True,
        label="Parking Ticket",
        inherit_from=[TICKET.kind],
    )
    await load_schema(db=db, schema=SchemaRoot(generics=[ticket], nodes=[speeding_ticket, parking_ticket]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node=ticket.kind, node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)

    ticket1 = await Node.init(db=db, schema=speeding_ticket.kind)
    await ticket1.new(db=db, title="ticket1", ticket_id={"from_pool": {"id": np1.id}})
    await ticket1.save(db=db)

    ticket2 = await Node.init(db=db, schema=parking_ticket.kind)
    await ticket2.new(db=db, title="ticket2", ticket_id={"from_pool": {"id": np1.id}})
    await ticket2.save(db=db)

    assert ticket1.ticket_id.value == 1
    assert ticket2.ticket_id.value == 2

    # If a resource is deleted the allocated number should be returned to the pool
    await ticket2.delete(db=db)
    recreated_ticket2 = await Node.init(db=db, schema=parking_ticket.kind)
    await recreated_ticket2.new(db=db, title="ticket2", ticket_id={"from_pool": {"id": np1.id}})
    await recreated_ticket2.save(db=db)
    assert recreated_ticket2.ticket_id.value == 2

    utilization = await resolve_number_pool_utilization(db=db, pool=np1, at=Timestamp(), branch=default_branch)
    assert utilization["edges"][0]["node"]["utilization"] == 20.0


async def test_allocate_from_number_pool_with_excluded_values(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema
):
    speeding_ticket = NodeSchema(
        name="SpeedingTicket",
        namespace="Testing",
        include_in_menu=True,
        label="Speeding Ticket",
        human_friendly_id=["title__value", "ticket_id__value"],
        attributes=[
            AttributeSchema(name="title", kind="Text", optional=False),
            AttributeSchema(name="description", kind="TextArea", optional=True),
            NumberAttributeSchema(
                name="ticket_id",
                kind="Number",
                optional=True,
                unique=True,
                parameters=NumberAttributeParameters(min_value=10, max_value=30, excluded_values="12,14-16"),
            ),
        ],
    )

    await load_schema(db=db, schema=SchemaRoot(nodes=[speeding_ticket]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(
        db=db, name="pool1", node=speeding_ticket.kind, node_attribute="ticket_id", start_range=10, end_range=30
    )
    await np1.save(db=db)

    tickets = []
    for _ in range(5):
        ticket = await Node.init(db=db, schema=speeding_ticket.kind)
        await ticket.new(db=db, title="ticket", ticket_id={"from_pool": {"id": np1.id}})
        await ticket.save(db=db)
        tickets.append(ticket)

    assert tickets[0].ticket_id.value == 10
    assert tickets[1].ticket_id.value == 11
    assert tickets[2].ticket_id.value == 13
    assert tickets[3].ticket_id.value == 17
    assert tickets[4].ticket_id.value == 18

    # If a resource is deleted the allocated number should be returned to the pool
    await tickets[0].delete(db=db)
    await tickets[1].delete(db=db)
    await tickets[2].delete(db=db)
    await tickets[3].delete(db=db)
    await tickets[4].delete(db=db)

    ticket = await Node.init(db=db, schema=speeding_ticket.kind)
    await ticket.new(db=db, title="ticket2", ticket_id={"from_pool": {"id": np1.id}})
    await ticket.save(db=db)
    assert ticket.ticket_id.value == 10

    utilization = await resolve_number_pool_utilization(db=db, pool=np1, at=Timestamp(), branch=default_branch)

    nb_values_used_in_pool = 1
    nb_excluded_values = 4
    total_pool_length = np1.end_range.value - np1.start_range.value + 1 - nb_excluded_values
    assert utilization["edges"][0]["node"]["utilization"] == nb_values_used_in_pool / total_pool_length * 100

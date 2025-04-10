from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.queries.resource_manager import resolve_number_pool_utilization
from tests.helpers.schema import TICKET, load_schema


async def test_allocate_from_number_pool(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    np1 = await Node.init(db=db, schema="CoreNumberPool")
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
    await ticket2.delete(db=db)
    recreated_ticket2 = await Node.init(db=db, schema=TICKET.kind)
    await recreated_ticket2.new(db=db, title="ticket2", ticket_id={"from_pool": {"id": np1.id}})
    await recreated_ticket2.save(db=db)
    assert recreated_ticket2.ticket_id.value == 2


async def test_resource_utilization(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    """
    Allocates:
    - 1 ticket in first number pool
    - 2 tickets in second number pool
    and verifies resource pool utilization.
    """

    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    np1 = await Node.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)

    ticket1_np1 = await Node.init(db=db, schema=TICKET.kind)
    await ticket1_np1.new(db=db, title="ticket1_np1", ticket_id={"from_pool": {"id": np1.id}})
    await ticket1_np1.save(db=db)

    np2 = await Node.init(db=db, schema="CoreNumberPool")
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

    np1 = await Node.init(db=db, schema="CoreNumberPool")
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

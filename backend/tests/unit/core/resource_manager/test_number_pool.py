from infrahub.core.branch import Branch
from infrahub.core.initialization import initialize_registry
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
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

from copy import deepcopy

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters
from infrahub.core.schema.attribute_schema import AttributeSchema, NumberAttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.queries.resource_manager import resolve_number_pool_utilization
from infrahub.pools.attribute_pool_applier_factory import build_attribute_pool_applier
from infrahub.pools.number import NumberUtilizationGetter
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_ranges import EffectiveSpace, NumberDomain
from tests.helpers.agnostic_edges import pool_reservation_edges
from tests.helpers.number_pool import (
    add_pool_range,
    create_range_only_pool,
    create_ticket,
    pool_lowest_free_number,
    pool_used_numbers,
    schema_domains,
    ticket_schema_with_parameters,
)
from tests.helpers.schema import TICKET, load_schema


async def test_allocate_from_number_pool(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)
    await add_pool_range(db=db, pool=np1, start=1, end=10)

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
    assert await pool_lowest_free_number(db=db, pool=np1, branch=default_branch) == 1

    recreated_ticket1 = await Node.init(db=db, schema=TICKET.kind)
    await recreated_ticket1.new(db=db, title="ticket1", ticket_id={"from_pool": {"id": np1.id}})
    await recreated_ticket1.save(db=db)
    assert recreated_ticket1.ticket_id.value == 1

    # Validate methods at the pool level
    assert await pool_used_numbers(db=db, pool=np1, branch=default_branch) == [1, 2]

    assert await pool_lowest_free_number(db=db, pool=np1, branch=default_branch) == 3


async def test_allocation_records_reservation_whether_pool_is_named_or_identified(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A pool referenced by name records its reservation exactly as one referenced by id does."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)

    created_by_id = await Node.init(db=db, schema=TICKET.kind)
    await created_by_id.new(db=db, title="by-id", ticket_id={"from_pool": {"id": pool.get_id()}})
    await created_by_id.save(db=db)

    created_by_name = await Node.init(db=db, schema=TICKET.kind)
    await created_by_name.new(db=db, title="by-name", ticket_id={"from_pool": {"id": "pool1"}})
    await created_by_name.save(db=db)

    updated_by_name = await Node.init(db=db, schema=TICKET.kind)
    await updated_by_name.new(db=db, title="updated-by-name", ticket_id=None)
    await updated_by_name.save(db=db)
    await updated_by_name.from_graphql(
        db=db, data={"ticket_id": {"from_pool": {"id": "pool1"}}}, pool_applier=build_attribute_pool_applier(db=db)
    )
    await updated_by_name.save(db=db)

    tickets = {"created by id": created_by_id, "created by name": created_by_name, "updated by name": updated_by_name}
    for label, ticket in tickets.items():
        attribute_id = ticket.get_attribute("ticket_id").id
        assert attribute_id is not None
        records = await pool_reservation_edges(db=db, pool_id=pool.get_id(), attribute_id=attribute_id)
        assert [record.is_open for record in records] == [True], f"no reservation record for the ticket {label}"

    assert await pool_used_numbers(db=db, pool=pool, branch=default_branch) == [1, 2, 3]


async def test_allocate_reuses_value_when_attribute_not_globally_unique(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Existing target values are skipped only when the attribute is globally unique."""
    schema = deepcopy(TICKET)
    next(attr for attr in schema.attributes if attr.name == "ticket_id").unique = False
    await load_schema(db=db, schema=SchemaRoot(nodes=[schema]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)
    await add_pool_range(db=db, pool=np1, start=1, end=10)

    # Created by hand inside the pool range, without going through the pool.
    manual_ticket = await Node.init(db=db, schema=TICKET.kind)
    await manual_ticket.new(db=db, title="manual", ticket_id=1)
    await manual_ticket.save(db=db)

    ticket = await Node.init(db=db, schema=TICKET.kind)
    await ticket.new(db=db, title="ticket", ticket_id={"from_pool": {"id": np1.id}})
    await ticket.save(db=db)

    assert ticket.ticket_id.value == 1


class TestNumberPoolAllocation:
    """Allocation against one unique ticket schema and a 1-10 pool, loaded once for the class.

    The methods share the loaded schema, pool and accumulated data, and run in definition order: each
    builds on the state the previous one leaves behind.
    """

    @pytest.fixture(scope="class")
    async def pool(self, db: InfrahubDatabase, register_core_models_schema_scope_class: SchemaBranch) -> CoreNumberPool:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        await initialize_registry(db=db)

        pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await pool.new(
            db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10
        )
        await pool.save(db=db)
        await add_pool_range(db=db, pool=pool, start=1, end=10)
        return pool

    @pytest.fixture(scope="class")
    async def present_ticket(self, db: InfrahubDatabase, pool: CoreNumberPool) -> Node:
        """A ticket created by hand at value 1, inside the pool range but never handed out by the pool."""
        ticket = await Node.init(db=db, schema=TICKET.kind)
        await ticket.new(db=db, title="manual", ticket_id=1)
        await ticket.save(db=db)
        return ticket

    async def test_taken_values_see_origin_branch_after_branch_point(
        self, db: InfrahubDatabase, pool: CoreNumberPool
    ) -> None:
        """A value added to the origin branch after the branch point counts as taken on the branch."""
        branch = await create_branch(db=db, branch_name="feat")

        # Created on the origin branch after the branch point.
        origin_ticket = await Node.init(db=db, schema=TICKET.kind)
        await origin_ticket.new(db=db, title="origin", ticket_id=5)
        await origin_ticket.save(db=db)

        repository = NumberPoolRepository(db=db)
        space = EffectiveSpace(ranges=await repository.get_pool_ranges(pool_id=pool.get_id()), domain=NumberDomain())
        assert await repository.get_taken(pool=pool, branch=branch, space=space) == {5}

    async def test_allocate_skips_value_already_present_on_target(
        self, db: InfrahubDatabase, pool: CoreNumberPool, present_ticket: Node
    ) -> None:
        """A value already present on the target kind but never handed out by the pool is skipped."""
        ticket = await Node.init(db=db, schema=TICKET.kind)
        await ticket.new(db=db, title="ticket", ticket_id={"from_pool": {"id": pool.id}})
        await ticket.save(db=db)

        # 1 is held by present_ticket, so the pool skips it and hands out the next free value.
        assert ticket.ticket_id.value == 2

    async def test_allocate_reuses_value_after_conflicting_target_deleted(
        self, db: InfrahubDatabase, pool: CoreNumberPool, present_ticket: Node
    ) -> None:
        """A value freed by deleting the conflicting target object becomes allocatable again."""
        await present_ticket.delete(db=db)

        ticket = await Node.init(db=db, schema=TICKET.kind)
        await ticket.new(db=db, title="reuse", ticket_id={"from_pool": {"id": pool.id}})
        await ticket.save(db=db)

        # Deleting present_ticket frees value 1, now the lowest available.
        assert ticket.ticket_id.value == 1


async def test_resource_utilization(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Each pool reports its own totals, and each range it holds reports its own figures underneath."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)

    np1 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np1.new(db=db, name="pool1", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np1.save(db=db)

    whole = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOLRANGE)
    await whole.new(db=db, start=1, end=10, pool=np1.get_id())
    await whole.save(db=db)

    ticket1_np1 = await Node.init(db=db, schema=TICKET.kind)
    await ticket1_np1.new(db=db, title="ticket1_np1", ticket_id={"from_pool": {"id": np1.id}})
    await ticket1_np1.save(db=db)

    np2 = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await np2.new(db=db, name="pool2", node="TestingTicket", node_attribute="ticket_id", start_range=1, end_range=10)
    await np2.save(db=db)

    lower = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOLRANGE)
    await lower.new(db=db, start=1, end=5, allocation_weight=10, pool=np2.get_id())
    await lower.save(db=db)

    upper = await Node.init(db=db, schema=InfrahubKind.NUMBERPOOLRANGE)
    await upper.new(db=db, start=6, end=10, pool=np2.get_id())
    await upper.save(db=db)

    for index in range(2):
        ticket = await Node.init(db=db, schema=TICKET.kind)
        await ticket.new(db=db, title=f"ticket{index}_np2", ticket_id={"from_pool": {"id": np2.id}})
        await ticket.save(db=db)

    utilization_np1 = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=default_branch), pool=np1, at=Timestamp(), branch=default_branch
    )

    assert utilization_np1 == {
        "count": 1,
        "utilization": 10,
        "utilization_default_branch": 10,
        "utilization_branches": 0,
        "edges": [
            {
                "node": {
                    "id": whole.get_id(),
                    "kind": InfrahubKind.NUMBERPOOLRANGE,
                    "display_label": "1 - 10",
                    "weight": 0,
                    "utilization": 10,
                    "utilization_default_branch": 10,
                    "utilization_branches": 0,
                }
            }
        ],
    }

    utilization_np2 = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=default_branch), pool=np2, at=Timestamp(), branch=default_branch
    )

    assert utilization_np2 == {
        "count": 2,
        "utilization": 20,
        "utilization_default_branch": 20,
        "utilization_branches": 0,
        "edges": [
            {
                "node": {
                    "id": lower.get_id(),
                    "kind": InfrahubKind.NUMBERPOOLRANGE,
                    "display_label": "1 - 5",
                    "weight": 10,
                    "utilization": 40,
                    "utilization_default_branch": 40,
                    "utilization_branches": 0,
                }
            },
            {
                "node": {
                    "id": upper.get_id(),
                    "kind": InfrahubKind.NUMBERPOOLRANGE,
                    "display_label": "6 - 10",
                    "weight": 0,
                    "utilization": 0,
                    "utilization_default_branch": 0,
                    "utilization_branches": 0,
                }
            },
        ],
    }


async def test_each_range_reports_the_numbers_its_branches_hold(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A number held on the default branch counts there only, even when a branch records it as well."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool = await create_range_only_pool(db=db)
    single = await add_pool_range(db=db, pool=pool, start=5, end=5, weight=10)
    upper = await add_pool_range(db=db, pool=pool, start=20, end=29)

    main_ticket = await Node.init(db=db, schema=TICKET.kind)
    await main_ticket.new(db=db, title="on main", ticket_id={"from_pool": {"id": pool.id}})
    await main_ticket.save(db=db)
    branch = await create_branch(db=db, branch_name="feat")
    branch_ticket = await Node.init(db=db, schema=TICKET.kind, branch=branch)
    await branch_ticket.new(db=db, title="on branch", ticket_id={"from_pool": {"id": pool.id}})
    await branch_ticket.save(db=db)
    assert (main_ticket.ticket_id.value, branch_ticket.ticket_id.value) == (5, 20)

    # Editing the number on the branch and restoring it leaves the branch its own record of 5.
    edited = await NodeManager.get_one(db=db, id=main_ticket.get_id(), branch=branch, raise_on_error=True)
    edited.ticket_id.value = 25
    await edited.save(db=db)
    edited.ticket_id.value = 5
    await edited.save(db=db)

    space = EffectiveSpace(
        ranges=await NumberPoolRepository(db=db).get_pool_ranges(pool_id=pool.get_id()), domain=NumberDomain()
    )
    getter = NumberUtilizationGetter(db=db, pool=pool, space=space, branch=branch)
    await getter.load_data()
    assert {(used.number, used.branch) for used in getter.used} == {(5, "main"), (5, "feat"), (20, "feat")}

    utilization = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=branch), pool=pool, at=Timestamp(), branch=branch
    )
    assert utilization == {
        "count": 2,
        "utilization": 2 / 11 * 100,
        "utilization_default_branch": 1 / 11 * 100,
        "utilization_branches": 1 / 11 * 100,
        "edges": [
            {
                "node": {
                    "id": single.get_id(),
                    "kind": InfrahubKind.NUMBERPOOLRANGE,
                    "display_label": "5 - 5",
                    "weight": 10,
                    "utilization": 100.0,
                    "utilization_default_branch": 100.0,
                    "utilization_branches": 0.0,
                }
            },
            {
                "node": {
                    "id": upper.get_id(),
                    "kind": InfrahubKind.NUMBERPOOLRANGE,
                    "display_label": "20 - 29",
                    "weight": 0,
                    "utilization": 10.0,
                    "utilization_default_branch": 0.0,
                    "utilization_branches": 10.0,
                }
            },
        ],
    }


async def test_utilization_measures_the_space_the_branch_schema_leaves(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A branch whose schema narrows the attribute reports the pool against the smaller space."""
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    await initialize_registry(db=db)
    pool = await create_range_only_pool(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)
    assert await create_ticket(db=db, kind=TICKET.kind, pool=pool) == 1

    branch = await create_branch(db=db, branch_name="narrow")
    narrowed = ticket_schema_with_parameters(NumberAttributeParameters(max_value=5))
    registry.schema.register_schema(schema=SchemaRoot(nodes=[narrowed]), branch=branch.name)

    on_main = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=default_branch), pool=pool, at=Timestamp(), branch=default_branch
    )
    on_branch = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=branch), pool=pool, at=Timestamp(), branch=branch
    )

    assert on_main["utilization"] == 10.0
    assert on_branch["utilization"] == 20.0
    assert [edge["node"]["utilization"] for edge in on_main["edges"]] == [10.0]
    assert [edge["node"]["utilization"] for edge in on_branch["edges"]] == [20.0]


async def test_allocate_from_number_pool_for_generic(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
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
    await add_pool_range(db=db, pool=np1, start=1, end=10)

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

    utilization = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=default_branch), pool=np1, at=Timestamp(), branch=default_branch
    )
    assert utilization["utilization"] == 20.0


async def test_allocate_from_number_pool_with_excluded_values(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
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
    await add_pool_range(db=db, pool=np1, start=10, end=30)

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
    assert ticket.get_attribute(name="ticket_id").value == 10

    utilization = await resolve_number_pool_utilization(
        db=db, domains=schema_domains(db=db, branch=default_branch), pool=np1, at=Timestamp(), branch=default_branch
    )

    nb_values_used_in_pool = 1
    nb_excluded_values = 4
    total_pool_length = np1.end_range.value - np1.start_range.value + 1 - nb_excluded_values
    assert utilization["utilization"] == nb_values_used_in_pool / total_pool_length * 100


@pytest.fixture
async def ticket_pool(db: InfrahubDatabase, ticket_schema: None) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(db=db, name="pool1", node=TICKET.kind, node_attribute="ticket_id", start_range=1, end_range=10)
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=10)
    return pool


@pytest.fixture
async def ticket(db: InfrahubDatabase, ticket_pool: CoreNumberPool) -> Node:
    """A ticket holding the pool's first number, and the record that accounts for it."""
    node = await Node.init(db=db, schema=TICKET.kind)
    await node.new(db=db, title="ticket1", ticket_id={"from_pool": {"id": ticket_pool.id}})
    await node.save(db=db)
    return node


class TestNumberPoolGetResource:
    """What `get_resource` does about a reservation the pool may already hold."""

    @staticmethod
    def _ticket_id_schema(ticket: Node) -> AttributeSchema:
        return ticket.get_schema().get_attribute(name="ticket_id")

    async def test_the_attribute_keeps_the_number_it_already_holds(
        self, db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool, ticket: Node
    ) -> None:
        assert ticket.get_attribute("ticket_id").value == 1

        again = await ticket_pool.get_resource(
            db=db,
            branch=default_branch,
            attribute=self._ticket_id_schema(ticket),
            identifier=ticket.get_id(),
            attribute_id=ticket.get_attribute("ticket_id").id,
        )

        assert again == 1, "asking again for an attribute the pool already accounts for must not draw a second number"
        assert await pool_used_numbers(db=db, pool=ticket_pool, branch=default_branch) == [1]

    async def test_an_attribute_with_no_vertex_yet_draws_a_number(
        self, db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool, ticket: Node
    ) -> None:
        """An object still being built has no attribute to carry a record, so there is nothing to look up."""
        drawn = await ticket_pool.get_resource(
            db=db,
            branch=default_branch,
            attribute=self._ticket_id_schema(ticket),
            identifier=ticket.get_id(),
            attribute_id=None,
        )

        assert drawn == 2, "with no attribute to anchor on the pool draws the next number rather than reusing one"
        assert await pool_used_numbers(db=db, pool=ticket_pool, branch=default_branch) == [1], (
            "and records nothing, because the caller writing the attribute writes the record"
        )

    async def test_a_record_another_pool_holds_is_not_its_own(
        self, db: InfrahubDatabase, default_branch: Branch, ticket_pool: CoreNumberPool, ticket: Node
    ) -> None:
        """The lookup is scoped to the asking pool, and the attribute ends up accounted for by one pool.

        An attribute belongs to a single pool, so drawing from another one hands the attribute over:
        the record the first pool held is closed as the second pool's is opened.
        """
        second_pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
        await second_pool.new(
            db=db, name="pool2", node=TICKET.kind, node_attribute="ticket_id", start_range=100, end_range=110
        )
        await second_pool.save(db=db)
        await add_pool_range(db=db, pool=second_pool, start=100, end=110)

        attribute_id = ticket.get_attribute("ticket_id").id
        drawn = await second_pool.get_resource(
            db=db,
            branch=default_branch,
            attribute=self._ticket_id_schema(ticket),
            identifier=ticket.get_id(),
            attribute_id=attribute_id,
        )

        assert drawn == 100, "the record belongs to the other pool, so this one draws from its own range"

        drawn_records = await pool_reservation_edges(db=db, pool_id=second_pool.get_id(), attribute_id=attribute_id)
        assert [record.is_open for record in drawn_records] == [True], (
            "drawing a number has to leave the record that accounts for it"
        )
        handed_over = await pool_reservation_edges(db=db, pool_id=ticket_pool.get_id(), attribute_id=attribute_id)
        assert [record.is_open for record in handed_over] == [False], (
            "the pool that held the attribute before must no longer account for it"
        )

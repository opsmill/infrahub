from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.query.resource_manager import NumberPoolGetAllocated, NumberPoolGetTrackingPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.agnostic_edges import EdgeState, attribute_edges
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET, load_schema

CREATE_TICKET = """
mutation CreateTicket($title: String!, $ticket_id: NumberAttributeCreate, $sequence: NumberAttributeCreate) {
    TestingTicketCreate(data: { title: { value: $title }, ticket_id: $ticket_id, sequence: $sequence }) {
        ok
        object { id ticket_id { value } sequence { value } }
    }
}
"""

UPDATE_TICKET = """
mutation UpdateTicket($id: String!, $ticket_id: NumberAttributeUpdate, $sequence: NumberAttributeUpdate) {
    TestingTicketUpdate(data: { id: $id, ticket_id: $ticket_id, sequence: $sequence }) {
        ok
        object { ticket_id { value } sequence { value } }
    }
}
"""

OPEN_IS_RESERVED_EDGES_OF_POOL = """
MATCH (:Node { uuid: $pool_id })-[reserved:IS_RESERVED]->(:Attribute)<-[:HAS_ATTRIBUTE]-(node:Node)
WHERE reserved.status = "active" AND reserved.to IS NULL
RETURN DISTINCT node.uuid AS node_id, elementId(reserved) AS edge_id, reserved.provenance AS provenance
"""

LIVE_IS_RESERVED_EDGES_BY_ATTRIBUTE = """
MATCH (:Node { uuid: $node_id })-[:HAS_ATTRIBUTE]->(attr:Attribute)<-[reserved:IS_RESERVED]-(pool:Node)
WHERE reserved.status = "active" AND reserved.to IS NULL
RETURN attr.name AS attribute_name, pool.uuid AS pool_id, reserved.provenance AS provenance
"""

# `sequence` is a second pooled number with no uniqueness constraint, so one schema serves every test.
TICKET_WITH_SEQUENCE = deepcopy(TICKET)
TICKET_WITH_SEQUENCE.attributes.append(AttributeSchema(name="sequence", kind="Number", optional=True))


async def _execute(
    db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]
) -> dict[str, Any] | None:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    assert not result.errors, result.errors
    return result.data


async def _create_ticket(db: InfrahubDatabase, branch: Branch, title: str, **fields: dict[str, Any]) -> dict[str, Any]:
    data = await _execute(db=db, branch=branch, source=CREATE_TICKET, variables={"title": title, **fields})
    assert data
    return data["TestingTicketCreate"]["object"]


async def _update_ticket(
    db: InfrahubDatabase, branch: Branch, node_id: str, **fields: dict[str, Any]
) -> dict[str, Any]:
    data = await _execute(db=db, branch=branch, source=UPDATE_TICKET, variables={"id": node_id, **fields})
    assert data
    return data["TestingTicketUpdate"]["object"]


async def _new_pool(
    db: InfrahubDatabase, name: str, start_range: int, end_range: int, node_attribute: str = "ticket_id"
) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(
        db=db,
        name=name,
        node=TICKET.kind,
        node_attribute=node_attribute,
        start_range=start_range,
        end_range=end_range,
    )
    await pool.save(db=db)
    return pool


async def _open_is_reserved_edges(db: InfrahubDatabase, pool: CoreNumberPool) -> set[tuple[str, str | None]]:
    """The holder and provenance of each open IS_RESERVED edge the pool has, on any attribute."""
    results = await db.execute_query(query=OPEN_IS_RESERVED_EDGES_OF_POOL, params={"pool_id": pool.get_id()})
    edge_ids = [result.get("edge_id") for result in results]
    assert len(edge_ids) == len(set(edge_ids))
    return {(result.get("node_id"), result.get("provenance")) for result in results}


async def _allocated(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool) -> list[tuple[str, str, int]]:
    """The holder, branch and value of every row the pool's in-use list reports."""
    query = await NumberPoolGetAllocated.init(db=db, pool=pool, branch=branch, branch_agnostic=True)
    await query.execute(db=db)
    return sorted((row.id, row.branch, row.value) for row in query.get_data())


async def _used(db: InfrahubDatabase, branch: Branch, pool: CoreNumberPool) -> list[int]:
    return await NumberPoolRepository(db=db).get_used(pool=pool, branch=branch)


async def _is_reserved_edges(db: InfrahubDatabase, node_id: str, attribute_name: str = "ticket_id") -> list[EdgeState]:
    edges = await attribute_edges(db=db, node_id=node_id, attribute_name=attribute_name)
    return sorted((edge for edge in edges if edge.edge_type == "IS_RESERVED"), key=lambda edge: edge.edge_id or "")


async def _tracking_pool_id(db: InfrahubDatabase, node_id: str) -> str | None:
    ticket = await NodeManager.get_one(db=db, id=node_id)
    assert ticket is not None
    attribute_id = ticket.get_attribute(name="ticket_id").id
    assert attribute_id is not None
    query = await NumberPoolGetTrackingPool.init(db=db, attribute_id=attribute_id)
    await query.execute(db=db)
    return query.get_pool_id()


@dataclass(frozen=True)
class ResendCase:
    name: str
    start_range: int
    create_payload: dict[str, Any]
    expected_value: int
    expected_provenance: str


class TestNumberPoolAttach:
    """Writes that name a number pool, through the GraphQL mutations, against the IS_RESERVED edges they leave.

    The schema is loaded once for the class and tickets accumulate across tests, so every test uses its own
    pools over a number range no other test uses.
    """

    @pytest.fixture(scope="class")
    async def main_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> Branch:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET_WITH_SEQUENCE]))
        await initialize_registry(db=db)
        default_branch_scope_class.update_schema_hash()
        return default_branch_scope_class

    async def test_attaching_a_number_records_it_as_provided(self, db: InfrahubDatabase, main_branch: Branch) -> None:
        pool = await _new_pool(db=db, name="attach", start_range=100, end_range=109)
        hand_set = await _create_ticket(db=db, branch=main_branch, title="attach-hand-set", ticket_id={"value": 105})
        allocated = await _create_ticket(
            db=db, branch=main_branch, title="attach-allocated", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert allocated["ticket_id"]["value"] == 100

        await _update_ticket(
            db=db, branch=main_branch, node_id=hand_set["id"], ticket_id={"value": 105, "from_pool": {"id": pool.id}}
        )
        changed = await _update_ticket(
            db=db, branch=main_branch, node_id=allocated["id"], ticket_id={"value": 107, "from_pool": {"id": pool.id}}
        )

        assert changed["ticket_id"]["value"] == 107
        assert await _open_is_reserved_edges(db=db, pool=pool) == {
            (hand_set["id"], "provided"),
            (allocated["id"], "provided"),
        }
        assert await _used(db=db, branch=main_branch, pool=pool) == [105, 107]

    async def test_a_number_a_uniqueness_constraint_holds_is_refused_by_the_constraint(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await _new_pool(db=db, name="unique", start_range=200, end_range=209)
        first = await _create_ticket(
            db=db, branch=main_branch, title="unique-first", ticket_id={"value": 200, "from_pool": {"id": pool.id}}
        )

        gql_params = await prepare_graphql_params(db=db, branch=main_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=CREATE_TICKET,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"title": "unique-second", "ticket_id": {"value": 200, "from_pool": {"id": pool.id}}},
        )

        assert result.errors
        assert str(result.errors[0].message) == "Violates uniqueness constraint 'ticket_id'"
        assert await NodeManager.query(db=db, schema=TICKET.kind, filters={"title__value": "unique-second"}) == []
        assert await _open_is_reserved_edges(db=db, pool=pool) == {(first["id"], "provided")}
        assert await _allocated(db=db, branch=main_branch, pool=pool) == [(first["id"], "main", 200)]

    async def test_each_holder_of_an_attached_duplicate_is_reported_and_the_number_is_not_reallocated(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await _new_pool(db=db, name="duplicate", start_range=300, end_range=309, node_attribute="sequence")
        first = await _create_ticket(
            db=db,
            branch=main_branch,
            title="duplicate-first",
            ticket_id={"value": 310},
            sequence={"value": 300, "from_pool": {"id": pool.id}},
        )
        second = await _create_ticket(
            db=db, branch=main_branch, title="duplicate-second", ticket_id={"value": 311}, sequence={"value": 300}
        )
        await _update_ticket(
            db=db, branch=main_branch, node_id=second["id"], sequence={"value": 300, "from_pool": {"id": pool.id}}
        )

        third = await _create_ticket(
            db=db,
            branch=main_branch,
            title="duplicate-third",
            ticket_id={"value": 312},
            sequence={"from_pool": {"id": pool.id}},
        )

        assert third["sequence"]["value"] == 301
        assert await _open_is_reserved_edges(db=db, pool=pool) == {
            (first["id"], "provided"),
            (second["id"], "provided"),
            (third["id"], "allocated"),
        }
        # One entry per IS_RESERVED edge, so each holder of the duplicate is listed.
        assert await _used(db=db, branch=main_branch, pool=pool) == [300, 300, 301]

    async def test_a_value_change_moves_the_number_the_pool_tracks(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await _new_pool(db=db, name="value-change", start_range=400, end_range=409)
        ticket = await _create_ticket(
            db=db, branch=main_branch, title="value-change", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 400
        before = await _is_reserved_edges(db=db, node_id=ticket["id"])

        changed = await _update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 405})

        assert changed["ticket_id"]["value"] == 405
        assert await _is_reserved_edges(db=db, node_id=ticket["id"]) == before
        assert await _allocated(db=db, branch=main_branch, pool=pool) == [(ticket["id"], "main", 405)]
        following = await _create_ticket(
            db=db, branch=main_branch, title="value-change-next", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert following["ticket_id"]["value"] == 400, "the number the ticket left behind goes back to the pool"

    async def test_a_value_change_on_a_branch_keeps_both_numbers_taken(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await _new_pool(db=db, name="branch-change", start_range=500, end_range=509)
        ticket = await _create_ticket(
            db=db, branch=main_branch, title="branch-change", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 500
        before = await _is_reserved_edges(db=db, node_id=ticket["id"])
        branch = await create_branch(branch_name="branch-change", db=db)

        changed = await _update_ticket(db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": 501})

        assert changed["ticket_id"]["value"] == 501
        assert await _is_reserved_edges(db=db, node_id=ticket["id"]) == before
        assert await _allocated(db=db, branch=main_branch, pool=pool) == [
            (ticket["id"], "branch-change", 501),
            (ticket["id"], "main", 500),
        ]
        following = await _create_ticket(
            db=db, branch=main_branch, title="branch-change-next", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert following["ticket_id"]["value"] == 502

    async def test_naming_another_pool_moves_the_attribute_and_allocates_from_it(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        # Pool B overlaps pool A, so a number left behind in A would still fall inside A's range and be reported.
        pool_a = await _new_pool(db=db, name="re-pool-a", start_range=600, end_range=649)
        pool_b = await _new_pool(db=db, name="re-pool-b", start_range=600, end_range=699)
        ticket = await _create_ticket(
            db=db, branch=main_branch, title="re-pool", ticket_id={"from_pool": {"id": pool_a.id}}
        )
        assert ticket["ticket_id"]["value"] == 600

        moved = await _update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": None, "from_pool": {"id": pool_b.id}}
        )

        assert moved["ticket_id"]["value"] == 601, "the ticket's own number is taken under the uniqueness constraint"
        assert await _open_is_reserved_edges(db=db, pool=pool_a) == set()
        assert await _allocated(db=db, branch=main_branch, pool=pool_a) == []
        assert await _open_is_reserved_edges(db=db, pool=pool_b) == {(ticket["id"], "allocated")}
        assert await _allocated(db=db, branch=main_branch, pool=pool_b) == [(ticket["id"], "main", 601)]
        assert await _tracking_pool_id(db=db, node_id=ticket["id"]) == pool_b.get_id()

    async def test_naming_another_pool_with_a_number_outside_the_first_pool_moves_the_attribute(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A number outside pool A's range is invisible to A's range-bounded reads, so only the edge shows it."""
        pool_a = await _new_pool(db=db, name="out-of-range-a", start_range=700, end_range=709)
        pool_c = await _new_pool(db=db, name="out-of-range-c", start_range=750, end_range=759)
        ticket = await _create_ticket(
            db=db, branch=main_branch, title="out-of-range", ticket_id={"from_pool": {"id": pool_a.id}}
        )

        moved = await _update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 755, "from_pool": {"id": pool_c.id}}
        )

        assert moved["ticket_id"]["value"] == 755
        assert await _open_is_reserved_edges(db=db, pool=pool_a) == set()
        assert await _open_is_reserved_edges(db=db, pool=pool_c) == {(ticket["id"], "provided")}
        assert await _used(db=db, branch=main_branch, pool=pool_c) == [755]
        assert await _tracking_pool_id(db=db, node_id=ticket["id"]) == pool_c.get_id()

    @pytest.mark.parametrize(
        "case",
        [
            ResendCase(
                name="provided",
                start_range=800,
                create_payload={"value": 805},
                expected_value=805,
                expected_provenance="provided",
            ),
            ResendCase(
                name="allocated",
                start_range=900,
                create_payload={},
                expected_value=900,
                expected_provenance="allocated",
            ),
        ],
        ids=lambda case: case.name,
    )
    async def test_resending_value_and_pool_writes_nothing(
        self, db: InfrahubDatabase, main_branch: Branch, case: ResendCase
    ) -> None:
        pool = await _new_pool(
            db=db, name=f"resend-{case.name}", start_range=case.start_range, end_range=case.start_range + 9
        )
        ticket = await _create_ticket(
            db=db,
            branch=main_branch,
            title=f"resend-{case.name}",
            ticket_id={**case.create_payload, "from_pool": {"id": pool.id}},
        )
        assert ticket["ticket_id"]["value"] == case.expected_value
        before = await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id")

        resent = await _update_ticket(
            db=db,
            branch=main_branch,
            node_id=ticket["id"],
            ticket_id={"value": case.expected_value, "from_pool": {"id": pool.id}},
        )

        assert resent["ticket_id"]["value"] == case.expected_value
        after = await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id")
        assert sorted(after, key=lambda edge: edge.edge_id or "") == sorted(before, key=lambda edge: edge.edge_id or "")
        assert await _open_is_reserved_edges(db=db, pool=pool) == {(ticket["id"], case.expected_provenance)}

    async def test_naming_the_pool_alone_on_a_hand_set_number_is_refused_and_writes_nothing(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await _new_pool(db=db, name="refused", start_range=1000, end_range=1009)
        ticket = await _create_ticket(db=db, branch=main_branch, title="refused", ticket_id={"value": 1003})

        gql_params = await prepare_graphql_params(db=db, branch=main_branch)
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TICKET,
            context_value=gql_params.context,
            root_value=None,
            variable_values={"id": ticket["id"], "ticket_id": {"from_pool": {"id": "refused"}}},
        )

        assert result.errors
        assert str(result.errors[0].message) == (
            "'ticket_id' already holds 1003, so 'from_pool' alone is ambiguous. Send the value together with 'from_pool' to "
            "have the pool track it, or send 'value: null' with 'from_pool' to discard it and allocate a new number. "
            "at ticket_id.from_pool"
        )
        assert await _is_reserved_edges(db=db, node_id=ticket["id"]) == []
        assert await _open_is_reserved_edges(db=db, pool=pool) == set()
        reloaded = await NodeManager.get_one(db=db, id=ticket["id"], branch=main_branch)
        assert reloaded is not None
        assert reloaded.get_attribute(name="ticket_id").value == 1003

    async def test_one_create_draws_and_attaches_from_two_pools(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        ticket_pool = await _new_pool(db=db, name="two-pools-ticket", start_range=1100, end_range=1109)
        sequence_pool = await _new_pool(
            db=db, name="two-pools-sequence", start_range=1150, end_range=1159, node_attribute="sequence"
        )

        created = await _create_ticket(
            db=db,
            branch=main_branch,
            title="two-pools",
            ticket_id={"from_pool": {"id": ticket_pool.id}},
            sequence={"value": 1155, "from_pool": {"id": "two-pools-sequence"}},
        )

        assert created["ticket_id"]["value"] == 1100
        assert created["sequence"]["value"] == 1155
        results = await db.execute_query(query=LIVE_IS_RESERVED_EDGES_BY_ATTRIBUTE, params={"node_id": created["id"]})
        assert sorted(
            (result.get("attribute_name"), result.get("pool_id"), result.get("provenance")) for result in results
        ) == [
            ("sequence", sequence_pool.get_id(), "provided"),
            ("ticket_id", ticket_pool.get_id(), "allocated"),
        ]
        assert await _used(db=db, branch=main_branch, pool=ticket_pool) == [1100]
        assert await _used(db=db, branch=main_branch, pool=sequence_pool) == [1155]

from collections import Counter
from typing import Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_account, create_branch
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_query_counter import CountingInfrahubDatabase

from .helpers import (
    AttributeRead,
    attribute_read,
    create_ticket,
    execute,
    new_pool,
    pooled_numbers,
    update_ticket,
)

CREATE_TICKET_READING_POOL = """
mutation CreateTicket($title: String!, $ticket_id: NumberAttributeCreate) {
    TestingTicketCreate(data: { title: { value: $title }, ticket_id: $ticket_id }) {
        ok
        object { id ticket_id { value source { id } from_pool { pool { id } provenance } } }
    }
}
"""

UPDATE_TICKET_READING_POOL = """
mutation UpdateTicket($id: String!, $ticket_id: NumberAttributeUpdate) {
    TestingTicketUpdate(data: { id: $id, ticket_id: $ticket_id }) {
        ok
        object { ticket_id { value source { id } from_pool { pool { id } provenance } } }
    }
}
"""

UPDATE_TICKET_WITH_PROFILE = """
mutation UpdateTicketProfile($id: String!, $profile_id: String!) {
    TestingTicketUpdate(data: { id: $id, sequence: { is_default: true }, profiles: [{ id: $profile_id }] }) {
        ok
        object { sequence { value is_from_profile } }
    }
}
"""

TICKET_SEQUENCE_WITH_PROFILE = """
query TicketSequence($id: ID!) {
    TestingTicket(ids: [$id]) {
        edges {
            node { sequence { value is_from_profile source { id } from_pool { pool { id } provenance } } }
        }
    }
}
"""

TICKETS_WITH_POOL = """
query TicketsWithPool($ids: [ID]) {
    TestingTicket(ids: $ids) {
        edges { node { ticket_id { value from_pool { pool { id display_label } provenance } } } }
    }
}
"""

TICKETS_WITH_PROVENANCE_ONLY = """
query TicketsWithProvenance($ids: [ID]) {
    TestingTicket(ids: $ids) {
        edges { node { ticket_id { value from_pool { provenance } } } }
    }
}
"""


class TestFromPoolRead:
    """What the `from_pool` output of a number attribute reports, and what `source` no longer reports.

    The schema is loaded once for the class and tickets accumulate across tests, so every test uses its own
    pools over a number range no other test uses.
    """

    async def test_an_allocated_number_reports_its_pool_as_allocated_and_no_source(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-allocated", start_range=4000, end_range=4009)

        ticket = await create_ticket(
            db=db, branch=main_branch, title="read-allocated", ticket_id={"from_pool": {"id": pool.id}}
        )

        reads = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"])
        assert reads["ticket_id"] == AttributeRead(4000, None, pool.get_id(), "ALLOCATED")

    async def test_a_provided_number_reports_the_source_the_user_set_beside_its_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-user-source", start_range=4100, end_range=4109)
        account = await create_account(db=db, name="read-user-source", password="read-user-source")

        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="read-user-source",
            ticket_id={"value": 4105, "from_pool": {"id": pool.id}, "source": account.id},
        )

        reads = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"])
        assert reads["ticket_id"] == AttributeRead(4105, account.id, pool.get_id(), "PROVIDED")

    async def test_a_number_no_pool_tracks_reports_no_pool(self, db: InfrahubDatabase, main_branch: Branch) -> None:
        await new_pool(db=db, name="read-untracked", start_range=4200, end_range=4209)

        ticket = await create_ticket(db=db, branch=main_branch, title="read-untracked", ticket_id={"value": 4205})

        reads = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"])
        assert reads["ticket_id"] == AttributeRead(4205, None, None, None)
        assert reads["sequence"] == AttributeRead(None, None, None, None)

    async def test_every_branch_reports_the_pool_whenever_the_branch_was_created(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-branches", start_range=4300, end_range=4309)
        ticket = await create_ticket(db=db, branch=main_branch, title="read-branches", ticket_id={"value": 4305})
        before = await create_branch(branch_name="read-branches-before", db=db)

        await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 4305, "from_pool": {"id": pool.id}}
        )
        after = await create_branch(branch_name="read-branches-after", db=db)

        for branch in (main_branch, before, after):
            reads = await pooled_numbers(db=db, branch=branch, node_id=ticket["id"])
            assert reads["ticket_id"] == AttributeRead(4305, None, pool.get_id(), "PROVIDED"), branch.name

    async def test_a_read_at_a_past_time_reports_the_pool_tracking_the_number_then(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-past", start_range=4400, end_range=4409)
        ticket = await create_ticket(db=db, branch=main_branch, title="read-past", ticket_id={"value": 4405})
        before_attach = Timestamp()
        await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 4405, "from_pool": {"id": pool.id}}
        )
        while_attached = Timestamp()
        await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"from_pool": None})

        now = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"])
        assert now["ticket_id"] == AttributeRead(4405, None, None, None)
        attached = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"], at=while_attached)
        assert attached["ticket_id"] == AttributeRead(4405, None, pool.get_id(), "PROVIDED")
        untracked = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"], at=before_attach)
        assert untracked["ticket_id"] == AttributeRead(4405, None, None, None)

    async def test_a_number_outside_the_range_or_null_still_reports_the_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-outside", start_range=4500, end_range=4509)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="read-outside", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 4500
        branch = await create_branch(branch_name="read-outside", db=db)

        await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 4590})
        await update_ticket(db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": None})

        on_main = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"])
        assert on_main["ticket_id"] == AttributeRead(4590, None, pool.get_id(), "PROVIDED")
        on_branch = await pooled_numbers(db=db, branch=branch, node_id=ticket["id"])
        assert on_branch["ticket_id"] == AttributeRead(None, None, pool.get_id(), "PROVIDED")

    async def test_a_number_inherited_from_a_profile_still_reports_the_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The profile becomes the number's source while the pool's record on the attribute stays open."""
        pool = await new_pool(db=db, name="read-profile", start_range=4700, end_range=4709, node_attribute="sequence")
        profile = await Node.init(db=db, schema="ProfileTestingTicket", branch=main_branch)
        await profile.new(db=db, profile_name="read-profile", profile_priority=1000, sequence=4705)
        await profile.save(db=db)
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="read-profile",
            ticket_id={"value": 4790},
            sequence={"from_pool": {"id": pool.id}},
        )
        assert ticket["sequence"]["value"] == 4700

        data = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_WITH_PROFILE,
            variables={"id": ticket["id"], "profile_id": profile.id},
        )

        assert data
        assert data["TestingTicketUpdate"]["object"]["sequence"] == {"value": 4705, "is_from_profile": True}
        data = await execute(
            db=db, branch=main_branch, source=TICKET_SEQUENCE_WITH_PROFILE, variables={"id": ticket["id"]}
        )
        assert data
        [edge] = data["TestingTicket"]["edges"]
        assert edge["node"]["sequence"]["is_from_profile"] is True
        assert attribute_read(edge["node"]["sequence"]) == AttributeRead(4705, profile.id, pool.get_id(), "PROVIDED")

    async def test_mutation_responses_report_the_record_the_mutation_wrote(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-mutation", start_range=4900, end_range=4909)

        created = await execute(
            db=db,
            branch=main_branch,
            source=CREATE_TICKET_READING_POOL,
            variables={"title": "read-mutation", "ticket_id": {"from_pool": {"id": pool.id}}},
        )
        assert created
        ticket = created["TestingTicketCreate"]["object"]
        assert attribute_read(ticket["ticket_id"]) == AttributeRead(4900, None, pool.get_id(), "ALLOCATED")

        attached = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_POOL,
            variables={"id": ticket["id"], "ticket_id": {"value": 4905, "from_pool": {"id": pool.id}}},
        )
        assert attached
        assert attribute_read(attached["TestingTicketUpdate"]["object"]["ticket_id"]) == AttributeRead(
            4905, None, pool.get_id(), "PROVIDED"
        )

        detached = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_POOL,
            variables={"id": ticket["id"], "ticket_id": {"from_pool": None}},
        )
        assert detached
        assert attribute_read(detached["TestingTicketUpdate"]["object"]["ticket_id"]) == AttributeRead(
            4905, None, None, None
        )

    async def test_reading_the_pools_of_a_page_of_numbers_costs_one_batched_pool_read(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The tracking record comes with the attribute read, and the pools it names are then loaded in one batch."""
        pool_a = await new_pool(db=db, name="read-count-a", start_range=5000, end_range=5009)
        pool_b = await new_pool(db=db, name="read-count-b", start_range=5010, end_range=5019)
        tickets: list[dict[str, Any]] = []
        for index, pool in enumerate((pool_a, pool_a, pool_b)):
            tickets.append(
                await create_ticket(
                    db=db, branch=main_branch, title=f"read-count-{index}", ticket_id={"from_pool": {"id": pool.id}}
                )
            )
        ids = [ticket["id"] for ticket in tickets]

        async def count_queries(source: str, node_ids: list[str]) -> tuple[Counter[str], list[dict[str, Any]]]:
            counting_db = CountingInfrahubDatabase.from_db(db=db)
            data = await execute(db=counting_db, branch=main_branch, source=source, variables={"ids": node_ids})
            assert data
            return counting_db.query_counts, data["TestingTicket"]["edges"]

        with_pools, edges = await count_queries(source=TICKETS_WITH_POOL, node_ids=ids)
        provenance_only, _ = await count_queries(source=TICKETS_WITH_PROVENANCE_ONLY, node_ids=ids)
        with_pools_one_ticket, _ = await count_queries(source=TICKETS_WITH_POOL, node_ids=ids[:1])

        assert sorted(
            (edge["node"]["ticket_id"]["value"], edge["node"]["ticket_id"]["from_pool"]["pool"]["display_label"])
            for edge in edges
        ) == [(5000, "read-count-a"), (5001, "read-count-a"), (5010, "read-count-b")]
        assert dict(with_pools - provenance_only) == {
            "node_list_get_info": 1,
            "node_list_get_attribute": 1,
            "node_list_get_relationship": 1,
        }, "the pools of the page are loaded with one batched node read"
        assert with_pools == with_pools_one_ticket, "the cost does not grow with the number of tickets"

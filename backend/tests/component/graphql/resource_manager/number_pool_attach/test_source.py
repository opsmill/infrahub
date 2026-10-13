from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_account, create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .helpers import (
    AttributeRead,
    attribute_read,
    create_ticket,
    execute,
    new_pool,
    pool_source,
    pooled_numbers,
    update_ticket,
)

CREATE_TICKET_READING_SOURCE = """
mutation CreateTicket($title: String!, $ticket_id: NumberAttributeCreate) {
    TestingTicketCreate(data: { title: { value: $title }, ticket_id: $ticket_id }) {
        ok
        object { id ticket_id { value source { id __typename } } }
    }
}
"""

UPDATE_TICKET_READING_SOURCE = """
mutation UpdateTicket($id: String!, $ticket_id: NumberAttributeUpdate) {
    TestingTicketUpdate(data: { id: $id, ticket_id: $ticket_id }) {
        ok
        object { ticket_id { value source { id __typename } } }
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
        edges { node { sequence { value is_from_profile source { id __typename } } } }
    }
}
"""


class TestPooledSourceRead:
    """What `source` reports on a number attribute: the pool tracking it ahead of any source the user set.

    The schema is loaded once for the class and tickets accumulate across tests, so every test uses its own
    pools over a number range no other test uses.
    """

    async def test_an_allocated_number_reports_its_pool_as_source(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-allocated", start_range=4000, end_range=4009)

        ticket = await create_ticket(
            db=db, branch=main_branch, title="read-allocated", ticket_id={"from_pool": {"id": pool.id}}
        )

        reads = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"])
        assert reads["ticket_id"] == pool_source(4000, pool)

    async def test_the_pool_is_reported_ahead_of_a_source_the_user_set(
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
        assert reads["ticket_id"] == pool_source(4105, pool)
        stored = await NodeManager.get_one(
            db=db, id=ticket["id"], branch=main_branch, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
        )
        stored_source = await stored.get_attribute("ticket_id").get_source(db=db)
        assert stored_source is not None
        assert stored_source.id == account.id, "the source the user set is kept, and is what the node reports"

    async def test_a_number_no_pool_tracks_reports_the_source_the_user_set_or_none(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        await new_pool(db=db, name="read-untracked", start_range=4200, end_range=4209)
        account = await create_account(db=db, name="read-untracked", password="read-untracked")

        with_source = await create_ticket(
            db=db, branch=main_branch, title="read-untracked", ticket_id={"value": 4205, "source": account.id}
        )
        without_source = await create_ticket(
            db=db, branch=main_branch, title="read-untracked-2", ticket_id={"value": 4206}
        )

        reads = await pooled_numbers(db=db, branch=main_branch, node_id=with_source["id"])
        assert reads["ticket_id"] == AttributeRead(4205, account.id, InfrahubKind.ACCOUNT)
        reads = await pooled_numbers(db=db, branch=main_branch, node_id=without_source["id"])
        assert reads["ticket_id"] == AttributeRead(4206, None, None)
        assert reads["sequence"] == AttributeRead(None, None, None)

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
            assert reads["ticket_id"] == pool_source(4305, pool), branch.name

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
        assert now["ticket_id"] == AttributeRead(4405, None, None)
        attached = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"], at=while_attached)
        assert attached["ticket_id"] == pool_source(4405, pool)
        untracked = await pooled_numbers(db=db, branch=main_branch, node_id=ticket["id"], at=before_attach)
        assert untracked["ticket_id"] == AttributeRead(4405, None, None)

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
        assert on_main["ticket_id"] == pool_source(4590, pool)
        on_branch = await pooled_numbers(db=db, branch=branch, node_id=ticket["id"])
        assert on_branch["ticket_id"] == pool_source(None, pool)

    async def test_a_number_inherited_from_a_profile_still_reports_the_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The profile becomes the stored source while the pool's record on the attribute stays open and wins."""
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
        assert attribute_read(edge["node"]["sequence"]) == pool_source(4705, pool)

    async def test_mutation_responses_report_the_pool_the_mutation_left_tracking_the_number(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-mutation", start_range=4900, end_range=4909)

        created = await execute(
            db=db,
            branch=main_branch,
            source=CREATE_TICKET_READING_SOURCE,
            variables={"title": "read-mutation", "ticket_id": {"from_pool": {"id": pool.id}}},
        )
        assert created
        ticket = created["TestingTicketCreate"]["object"]
        assert attribute_read(ticket["ticket_id"]) == pool_source(4900, pool)

        attached = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"value": 4905, "from_pool": {"id": pool.id}}},
        )
        assert attached
        assert attribute_read(attached["TestingTicketUpdate"]["object"]["ticket_id"]) == pool_source(4905, pool)

        value_only = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"value": 4906}},
        )
        assert value_only
        assert attribute_read(value_only["TestingTicketUpdate"]["object"]["ticket_id"]) == pool_source(4906, pool), (
            "a write naming no pool still reports the pool tracking the number"
        )

        detached = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"from_pool": None}},
        )
        assert detached
        assert attribute_read(detached["TestingTicketUpdate"]["object"]["ticket_id"]) == AttributeRead(4906, None, None)

from collections import Counter
from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_account, create_branch
from infrahub.core.manager import NodeManager
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

TICKETS_WITH_SOURCE = """
query TicketsWithSource($ids: [ID]) {
    TestingTicket(ids: $ids) {
        edges { node { ticket_id { value source { id display_label } } } }
    }
}
"""


TITLES_WITH_SOURCE = """
query TitlesWithSource($ids: [ID]) {
    TestingTicket(ids: $ids) {
        edges { node { title { value source { id display_label } } } }
    }
}
"""


TITLES_WITH_OWNER = """
query TitlesWithOwner($ids: [ID]) {
    TestingTicket(ids: $ids) {
        edges { node { title { value owner { id display_label } } } }
    }
}
"""

TITLES_WITH_SOURCE_AND_OWNER = """
query TitlesWithSourceAndOwner($ids: [ID]) {
    TestingTicket(ids: $ids) {
        edges { node { title { value source { id display_label } owner { id display_label } } } }
    }
}
"""

CREATE_TICKET_WITH_TITLE_SOURCE = """
mutation CreateTicket($title: TextAttributeCreate!, $ticket_id: NumberAttributeCreate) {
    TestingTicketCreate(data: { title: $title, ticket_id: $ticket_id }) {
        ok
        object { id }
    }
}
"""

PAGE_READ_WITH_ONE_BATCHED_OBJECT_READ = {
    "node_get_list": 1,
    "node_list_get_info": 2,
    "node_list_get_attribute": 2,
    "node_list_get_relationship": 2,
}
"""The page read is one of each. The attributes name other objects, which account for the second reads."""


async def count_queries(
    db: InfrahubDatabase, branch: Branch, source: str, object_ids: list[str]
) -> tuple[Counter[str], list[dict[str, Any]]]:
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    data = await execute(db=counting_db, branch=branch, source=source, variables={"ids": object_ids})
    assert data
    return counting_db.query_counts, data["TestingTicket"]["edges"]


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
        second_pool = await new_pool(db=db, name="read-mutation-2", start_range=4910, end_range=4919)

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

        re_pooled = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"value": 4915, "from_pool": {"id": second_pool.id}}},
        )
        assert re_pooled
        assert attribute_read(re_pooled["TestingTicketUpdate"]["object"]["ticket_id"]) == pool_source(
            4915, second_pool
        ), "a write naming another pool reports that pool"

        detached = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"from_pool": None}},
        )
        assert detached
        assert attribute_read(detached["TestingTicketUpdate"]["object"]["ticket_id"]) == AttributeRead(4915, None, None)

    async def test_mutation_responses_report_the_pool_ahead_of_a_source_the_user_set(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="read-mutation-user-source", start_range=4920, end_range=4929)
        second_pool = await new_pool(db=db, name="read-mutation-user-source-2", start_range=4930, end_range=4939)
        account = await create_account(db=db, name="read-mutation-user-source", password="read-mutation-user-source")

        created = await execute(
            db=db,
            branch=main_branch,
            source=CREATE_TICKET_READING_SOURCE,
            variables={
                "title": "read-mutation-user-source",
                "ticket_id": {"value": 4923, "from_pool": {"id": pool.id}, "source": account.id},
            },
        )
        assert created
        ticket = created["TestingTicketCreate"]["object"]
        assert attribute_read(ticket["ticket_id"]) == pool_source(4923, pool)

        re_pooled = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"value": 4933, "from_pool": {"id": second_pool.id}}},
        )
        assert re_pooled
        assert attribute_read(re_pooled["TestingTicketUpdate"]["object"]["ticket_id"]) == pool_source(4933, second_pool)

        detached = await execute(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET_READING_SOURCE,
            variables={"id": ticket["id"], "ticket_id": {"from_pool": None}},
        )
        assert detached
        assert attribute_read(detached["TestingTicketUpdate"]["object"]["ticket_id"]) == AttributeRead(
            4933, account.id, InfrahubKind.ACCOUNT
        ), "once no pool tracks the number, the source the user set is what the response reports"

    async def test_reading_the_sources_of_a_page_of_numbers_costs_one_batched_object_read(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The tracking pool comes with the attribute read, and the pools a page names are loaded in one batch."""
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

        with_source, edges = await count_queries(db=db, branch=main_branch, source=TICKETS_WITH_SOURCE, object_ids=ids)

        assert sorted(
            (edge["node"]["ticket_id"]["value"], edge["node"]["ticket_id"]["source"]["display_label"]) for edge in edges
        ) == [(5000, "read-count-a"), (5001, "read-count-a"), (5010, "read-count-b")]
        assert dict(with_source) == PAGE_READ_WITH_ONE_BATCHED_OBJECT_READ, (
            "the pools of the page are loaded with one batched object read"
        )

    async def test_reading_the_sources_of_a_page_of_text_values_costs_one_batched_object_read(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A stored source on any attribute kind goes through the same batched load as a pool."""
        account = await create_account(db=db, name="read-count-text", password="read-count-text")
        ids: list[str] = []
        for index in range(3):
            created = await execute(
                db=db,
                branch=main_branch,
                source=CREATE_TICKET_WITH_TITLE_SOURCE,
                variables={
                    "title": {"value": f"read-count-text-{index}", "source": account.id},
                    "ticket_id": {"value": 5100 + index},
                },
            )
            assert created
            ids.append(created["TestingTicketCreate"]["object"]["id"])

        with_source, edges = await count_queries(db=db, branch=main_branch, source=TITLES_WITH_SOURCE, object_ids=ids)

        assert {edge["node"]["title"]["source"]["id"] for edge in edges} == {account.id}
        assert dict(with_source) == PAGE_READ_WITH_ONE_BATCHED_OBJECT_READ, (
            "the sources of the page are loaded with one batched object read"
        )

    async def test_reading_the_owners_of_a_page_costs_one_batched_object_read(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """An owner goes through the same batched load as a source."""
        account = await create_account(db=db, name="read-count-owner", password="read-count-owner")
        ids: list[str] = []
        for index in range(3):
            created = await execute(
                db=db,
                branch=main_branch,
                source=CREATE_TICKET_WITH_TITLE_SOURCE,
                variables={
                    "title": {"value": f"read-count-owner-{index}", "owner": account.id},
                    "ticket_id": {"value": 5200 + index},
                },
            )
            assert created
            ids.append(created["TestingTicketCreate"]["object"]["id"])

        with_owner, edges = await count_queries(db=db, branch=main_branch, source=TITLES_WITH_OWNER, object_ids=ids)

        assert {edge["node"]["title"]["owner"]["id"] for edge in edges} == {account.id}
        assert dict(with_owner) == PAGE_READ_WITH_ONE_BATCHED_OBJECT_READ, (
            "the owners of the page are loaded with one batched object read"
        )

    async def test_an_object_that_is_both_source_and_owner_is_loaded_once_for_a_page(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """Both fields share one loader, so the same sub-selection on both costs one read for the page."""
        account = await create_account(db=db, name="read-count-both", password="read-count-both")
        ids: list[str] = []
        for index in range(3):
            created = await execute(
                db=db,
                branch=main_branch,
                source=CREATE_TICKET_WITH_TITLE_SOURCE,
                variables={
                    "title": {"value": f"read-count-both-{index}", "source": account.id, "owner": account.id},
                    "ticket_id": {"value": 5300 + index},
                },
            )
            assert created
            ids.append(created["TestingTicketCreate"]["object"]["id"])

        with_both, edges = await count_queries(
            db=db, branch=main_branch, source=TITLES_WITH_SOURCE_AND_OWNER, object_ids=ids
        )

        assert {(edge["node"]["title"]["source"]["id"], edge["node"]["title"]["owner"]["id"]) for edge in edges} == {
            (account.id, account.id)
        }
        assert dict(with_both) == PAGE_READ_WITH_ONE_BATCHED_OBJECT_READ, (
            "the sources and owners of the page are loaded together, with one batched object read"
        )

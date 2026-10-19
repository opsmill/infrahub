from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, MetadataOptions
from infrahub.core.initialization import create_account, create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import TICKET, load_schema

from .helpers import (
    AttributeRead,
    attribute_read,
    create_ticket,
    execute,
    new_pool,
    pool_source,
    pooled_numbers,
    tracking_pool_id,
    update_ticket,
    used_numbers,
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
        """The profile is the stored source on a branch while the pool's record on the attribute stays open and wins.

        A tracked number cannot be reset to take a profile's value, so the branch takes it before the pool tracks it.
        """
        pool = await new_pool(db=db, name="read-profile", start_range=4700, end_range=4709, node_attribute="sequence")
        profile = await Node.init(db=db, schema="ProfileTestingTicket", branch=main_branch)
        await profile.new(db=db, profile_name="read-profile", profile_priority=1000, sequence=4705)
        await profile.save(db=db)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="read-profile", ticket_id={"value": 4790}, sequence={"value": 4700}
        )
        branch = await create_branch(branch_name="read-profile", db=db)

        data = await execute(
            db=db,
            branch=branch,
            source=UPDATE_TICKET_WITH_PROFILE,
            variables={"id": ticket["id"], "profile_id": profile.id},
        )
        assert data
        assert data["TestingTicketUpdate"]["object"]["sequence"] == {"value": 4705, "is_from_profile": True}
        await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], sequence={"value": 4700, "from_pool": {"id": pool.id}}
        )

        data = await execute(db=db, branch=branch, source=TICKET_SEQUENCE_WITH_PROFILE, variables={"id": ticket["id"]})
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


CREATE_TICKET_WITH_PROFILE = """
mutation CreateTicketProfile($title: String!, $ticket_id: NumberAttributeCreate!, $profile_id: String!) {
    TestingTicketCreate(
        data: { title: { value: $title }, ticket_id: $ticket_id, profiles: [{ id: $profile_id }] }
    ) {
        ok
        object { id sequence { value is_from_profile } }
    }
}
"""

ASSIGN_PROFILE = """
mutation AssignProfile($id: String!, $profile_id: String!) {
    TestingTicketUpdate(data: { id: $id, profiles: [{ id: $profile_id }] }) {
        ok
    }
}
"""

REFRESH_PROFILES = """
mutation RefreshProfiles($id: String!) {
    InfrahubProfilesRefresh(data: { id: $id }) { ok }
}
"""

TICKET_WITH_DEFAULTED_SEQUENCE = deepcopy(TICKET)
TICKET_WITH_DEFAULTED_SEQUENCE.attributes.append(
    AttributeSchema(name="sequence", kind="Number", optional=True, default_value=4850)
)


async def new_profile(db: InfrahubDatabase, branch: Branch, name: str, sequence: int) -> Node:
    profile = await Node.init(db=db, schema="ProfileTestingTicket", branch=branch)
    await profile.new(db=db, profile_name=name, profile_priority=1000, sequence=sequence)
    await profile.save(db=db)
    return profile


async def edit_profile_sequence(db: InfrahubDatabase, branch: Branch, profile: Node, sequence: int) -> None:
    stored = await NodeManager.get_one(db=db, id=profile.id, branch=branch)
    assert stored is not None
    stored.get_attribute(name="sequence").value = sequence
    await stored.save(db=db)


async def refresh_profiles(db: InfrahubDatabase, branch: Branch, node_id: str) -> None:
    data = await execute(db=db, branch=branch, source=REFRESH_PROFILES, variables={"id": node_id})
    assert data
    assert data["InfrahubProfilesRefresh"]["ok"] is True


async def sequence_with_profile_flag(db: InfrahubDatabase, branch: Branch, node_id: str) -> dict[str, Any]:
    data = await execute(db=db, branch=branch, source=TICKET_SEQUENCE_WITH_PROFILE, variables={"id": node_id})
    assert data
    [edge] = data["TestingTicket"]["edges"]
    return edge["node"]["sequence"]


@dataclass(frozen=True)
class AttachedTicket:
    pool: CoreNumberPool
    profile: Node
    ticket_id: str


class TestProfileCannotMoveAnAttachedNumber:
    """An attach takes the number away from the profile or schema default that supplied it, so a profile leaves it alone.

    The schema gives `sequence` a default, and each starting state is set up once for the class over a number range no
    other test uses.
    """

    @pytest.fixture(scope="class")
    async def main_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> Branch:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET_WITH_DEFAULTED_SEQUENCE]))
        await initialize_registry(db=db)
        default_branch_scope_class.update_schema_hash()
        return default_branch_scope_class

    @pytest.fixture(scope="class")
    async def attached_profile_number(self, db: InfrahubDatabase, main_branch: Branch) -> AttachedTicket:
        pool = await new_pool(db=db, name="attach-profile", start_range=6000, end_range=6009, node_attribute="sequence")
        profile = await new_profile(db=db, branch=main_branch, name="attach-profile", sequence=6005)
        data = await execute(
            db=db,
            branch=main_branch,
            source=CREATE_TICKET_WITH_PROFILE,
            variables={"title": "attach-profile", "ticket_id": {"value": 6050}, "profile_id": profile.id},
        )
        assert data
        ticket = data["TestingTicketCreate"]["object"]
        assert ticket["sequence"] == {"value": 6005, "is_from_profile": True}

        await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], sequence={"value": 6005, "from_pool": {"id": pool.id}}
        )
        return AttachedTicket(pool=pool, profile=profile, ticket_id=ticket["id"])

    @pytest.fixture(scope="class")
    async def attached_schema_default(self, db: InfrahubDatabase, main_branch: Branch) -> AttachedTicket:
        pool = await new_pool(db=db, name="attach-default", start_range=4850, end_range=4859, node_attribute="sequence")
        ticket = await create_ticket(db=db, branch=main_branch, title="attach-default")
        assert ticket["sequence"] == {"value": 4850}
        await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], sequence={"value": 4850, "from_pool": {"id": pool.id}}
        )
        profile = await new_profile(db=db, branch=main_branch, name="attach-default", sequence=4855)

        data = await execute(
            db=db, branch=main_branch, source=ASSIGN_PROFILE, variables={"id": ticket["id"], "profile_id": profile.id}
        )
        assert data
        assert data["TestingTicketUpdate"]["ok"] is True
        return AttachedTicket(pool=pool, profile=profile, ticket_id=ticket["id"])

    async def test_an_attached_number_is_no_longer_reported_as_from_the_profile(
        self, db: InfrahubDatabase, main_branch: Branch, attached_profile_number: AttachedTicket
    ) -> None:
        sequence = await sequence_with_profile_flag(
            db=db, branch=main_branch, node_id=attached_profile_number.ticket_id
        )

        assert sequence["is_from_profile"] is False
        assert attribute_read(sequence) == pool_source(6005, attached_profile_number.pool)

    async def test_refreshing_an_edited_profile_does_not_move_an_attached_number(
        self, db: InfrahubDatabase, main_branch: Branch, attached_profile_number: AttachedTicket
    ) -> None:
        pool, ticket_id = attached_profile_number.pool, attached_profile_number.ticket_id

        await edit_profile_sequence(db=db, branch=main_branch, profile=attached_profile_number.profile, sequence=6900)
        await refresh_profiles(db=db, branch=main_branch, node_id=ticket_id)

        sequence = await sequence_with_profile_flag(db=db, branch=main_branch, node_id=ticket_id)
        assert sequence["is_from_profile"] is False
        assert attribute_read(sequence) == pool_source(6005, pool)
        assert await tracking_pool_id(db=db, node_id=ticket_id, attribute_name="sequence") == pool.id
        assert 6005 in await used_numbers(db=db, branch=main_branch, pool=pool)

    async def test_applying_a_profile_does_not_change_an_attached_schema_default(
        self, db: InfrahubDatabase, main_branch: Branch, attached_schema_default: AttachedTicket
    ) -> None:
        pool, ticket_id = attached_schema_default.pool, attached_schema_default.ticket_id

        await refresh_profiles(db=db, branch=main_branch, node_id=ticket_id)

        sequence = await sequence_with_profile_flag(db=db, branch=main_branch, node_id=ticket_id)
        assert sequence["is_from_profile"] is False
        assert attribute_read(sequence) == pool_source(4850, pool)
        assert await tracking_pool_id(db=db, node_id=ticket_id, attribute_name="sequence") == pool.id

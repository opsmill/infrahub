from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.agnostic_edges import TEST_ACTOR_ID, attribute_edges, node_metadata
from tests.helpers.graphql import graphql
from tests.helpers.schema import TICKET

from .helpers import (
    CREATE_TICKET,
    DELETE_POOL,
    LIVE_IS_RESERVED_EDGES_BY_ATTRIBUTE,
    SECOND_ACTOR_ID,
    THIRD_ACTOR_ID,
    UPDATE_TICKET,
    allocated_rows,
    create_ticket,
    execute,
    is_reserved_edges,
    new_pool,
    open_is_reserved_edges,
    pooled_sources,
    session_for,
    tracking_pool_id,
    update_ticket,
    used_numbers,
)


@dataclass(frozen=True)
class ResendCase:
    name: str
    start_range: int
    create_payload: dict[str, Any]
    expected_value: int
    expected_provenance: str


@dataclass(frozen=True)
class ReattachCase:
    name: str
    start_range: int
    reattach_payload: dict[str, Any]
    """What the write after the detach sends besides `from_pool`."""
    expected_value: int
    expected_provenance: str


class TestNumberPoolAttach:
    """Writes that name a number pool, through the GraphQL mutations, against the IS_RESERVED edges they leave.

    The schema is loaded once for the class and tickets accumulate across tests, so every test uses its own
    pools over a number range no other test uses.
    """

    async def test_attaching_a_number_records_it_as_provided(self, db: InfrahubDatabase, main_branch: Branch) -> None:
        pool = await new_pool(db=db, name="attach", start_range=100, end_range=109)
        hand_set = await create_ticket(db=db, branch=main_branch, title="attach-hand-set", ticket_id={"value": 105})
        allocated = await create_ticket(
            db=db, branch=main_branch, title="attach-allocated", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert allocated["ticket_id"]["value"] == 100

        await update_ticket(
            db=db, branch=main_branch, node_id=hand_set["id"], ticket_id={"value": 105, "from_pool": {"id": pool.id}}
        )
        changed = await update_ticket(
            db=db, branch=main_branch, node_id=allocated["id"], ticket_id={"value": 107, "from_pool": {"id": pool.id}}
        )

        assert changed["ticket_id"]["value"] == 107
        assert await open_is_reserved_edges(db=db, pool=pool) == {
            (hand_set["id"], "provided"),
            (allocated["id"], "provided"),
        }
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [105, 107]

    async def test_a_number_a_uniqueness_constraint_holds_is_refused_by_the_constraint(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="unique", start_range=200, end_range=209)
        first = await create_ticket(
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
        assert await open_is_reserved_edges(db=db, pool=pool) == {(first["id"], "provided")}
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [(first["id"], "main", 200)]

    async def test_each_holder_of_an_attached_duplicate_is_reported_and_the_number_is_not_reallocated(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="duplicate", start_range=300, end_range=309, node_attribute="sequence")
        first = await create_ticket(
            db=db,
            branch=main_branch,
            title="duplicate-first",
            ticket_id={"value": 310},
            sequence={"value": 300, "from_pool": {"id": pool.id}},
        )
        second = await create_ticket(
            db=db, branch=main_branch, title="duplicate-second", ticket_id={"value": 311}, sequence={"value": 300}
        )
        await update_ticket(
            db=db, branch=main_branch, node_id=second["id"], sequence={"value": 300, "from_pool": {"id": pool.id}}
        )

        third = await create_ticket(
            db=db,
            branch=main_branch,
            title="duplicate-third",
            ticket_id={"value": 312},
            sequence={"from_pool": {"id": pool.id}},
        )

        assert third["sequence"]["value"] == 301
        assert await open_is_reserved_edges(db=db, pool=pool) == {
            (first["id"], "provided"),
            (second["id"], "provided"),
            (third["id"], "allocated"),
        }
        # One entry per IS_RESERVED edge, so each holder of the duplicate is listed.
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [300, 300, 301]

    async def test_a_value_change_moves_the_number_the_pool_tracks(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="value-change", start_range=400, end_range=409)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="value-change", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 400
        before = await is_reserved_edges(db=db, node_id=ticket["id"])

        changed = await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 405})

        assert changed["ticket_id"]["value"] == 405
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [(ticket["id"], "main", 405)]
        following = await create_ticket(
            db=db, branch=main_branch, title="value-change-next", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert following["ticket_id"]["value"] == 400, "the number the ticket left behind goes back to the pool"

    async def test_a_value_change_on_a_branch_keeps_both_numbers_taken(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="branch-change", start_range=500, end_range=509)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="branch-change", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 500
        before = await is_reserved_edges(db=db, node_id=ticket["id"])
        branch = await create_branch(branch_name="branch-change", db=db)

        changed = await update_ticket(db=db, branch=branch, node_id=ticket["id"], ticket_id={"value": 501})

        assert changed["ticket_id"]["value"] == 501
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [
            (ticket["id"], "branch-change", 501),
            (ticket["id"], "main", 500),
        ]
        following = await create_ticket(
            db=db, branch=main_branch, title="branch-change-next", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert following["ticket_id"]["value"] == 502

    async def test_naming_another_pool_moves_the_attribute_and_allocates_from_it(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        # Pool B overlaps pool A, so a number left behind in A would still fall inside A's range and be reported.
        pool_a = await new_pool(db=db, name="re-pool-a", start_range=600, end_range=649)
        pool_b = await new_pool(db=db, name="re-pool-b", start_range=600, end_range=699)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="re-pool", ticket_id={"from_pool": {"id": pool_a.id}}
        )
        assert ticket["ticket_id"]["value"] == 600

        moved = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": None, "from_pool": {"id": pool_b.id}}
        )

        assert moved["ticket_id"]["value"] == 601, "the ticket's own number is taken under the uniqueness constraint"
        assert await open_is_reserved_edges(db=db, pool=pool_a) == set()
        assert await allocated_rows(db=db, branch=main_branch, pool=pool_a) == []
        assert await open_is_reserved_edges(db=db, pool=pool_b) == {(ticket["id"], "allocated")}
        assert await allocated_rows(db=db, branch=main_branch, pool=pool_b) == [(ticket["id"], "main", 601)]
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == pool_b.get_id()

    async def test_naming_another_pool_with_a_number_outside_the_first_pool_moves_the_attribute(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """A number outside pool A's range is invisible to A's range-bounded reads, so only the edge shows it."""
        pool_a = await new_pool(db=db, name="out-of-range-a", start_range=700, end_range=709)
        pool_c = await new_pool(db=db, name="out-of-range-c", start_range=750, end_range=759)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="out-of-range", ticket_id={"from_pool": {"id": pool_a.id}}
        )

        moved = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 755, "from_pool": {"id": pool_c.id}}
        )

        assert moved["ticket_id"]["value"] == 755
        assert await open_is_reserved_edges(db=db, pool=pool_a) == set()
        assert await open_is_reserved_edges(db=db, pool=pool_c) == {(ticket["id"], "provided")}
        assert await used_numbers(db=db, branch=main_branch, pool=pool_c) == [755]
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == pool_c.get_id()

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
        pool = await new_pool(
            db=db, name=f"resend-{case.name}", start_range=case.start_range, end_range=case.start_range + 9
        )
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title=f"resend-{case.name}",
            ticket_id={**case.create_payload, "from_pool": {"id": pool.id}},
        )
        assert ticket["ticket_id"]["value"] == case.expected_value
        before = await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id")

        resent = await update_ticket(
            db=db,
            branch=main_branch,
            node_id=ticket["id"],
            ticket_id={"value": case.expected_value, "from_pool": {"id": pool.id}},
        )

        assert resent["ticket_id"]["value"] == case.expected_value
        after = await attribute_edges(db=db, node_id=ticket["id"], attribute_name="ticket_id")
        assert sorted(after, key=lambda edge: edge.edge_id or "") == sorted(before, key=lambda edge: edge.edge_id or "")
        assert await open_is_reserved_edges(db=db, pool=pool) == {(ticket["id"], case.expected_provenance)}

    async def test_naming_the_pool_alone_on_a_hand_set_number_is_refused_and_writes_nothing(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="refused", start_range=1000, end_range=1009)
        ticket = await create_ticket(db=db, branch=main_branch, title="refused", ticket_id={"value": 1003})

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
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == []
        assert await open_is_reserved_edges(db=db, pool=pool) == set()
        reloaded = await NodeManager.get_one(db=db, id=ticket["id"], branch=main_branch)
        assert reloaded is not None
        assert reloaded.get_attribute(name="ticket_id").value == 1003

    async def test_one_create_draws_and_attaches_from_two_pools(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        ticket_pool = await new_pool(db=db, name="two-pools-ticket", start_range=1100, end_range=1109)
        sequence_pool = await new_pool(
            db=db, name="two-pools-sequence", start_range=1150, end_range=1159, node_attribute="sequence"
        )

        created = await create_ticket(
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
        assert await used_numbers(db=db, branch=main_branch, pool=ticket_pool) == [1100]
        assert await used_numbers(db=db, branch=main_branch, pool=sequence_pool) == [1155]

    async def test_detaching_a_number_keeps_it_on_the_object_and_frees_it_in_the_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="detach", start_range=1200, end_range=1209, node_attribute="sequence")
        detached = await create_ticket(
            db=db,
            branch=main_branch,
            title="detach",
            ticket_id={"value": 1290},
            sequence={"from_pool": {"id": pool.id}},
        )
        kept = await create_ticket(
            db=db,
            branch=main_branch,
            title="detach-kept",
            ticket_id={"value": 1291},
            sequence={"from_pool": {"id": pool.id}},
        )
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [1200, 1201]

        changed = await update_ticket(db=db, branch=main_branch, node_id=detached["id"], sequence={"from_pool": None})

        assert changed["sequence"]["value"] == 1200
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [1201]
        assert await open_is_reserved_edges(db=db, pool=pool) == {(kept["id"], "allocated")}
        [closed] = await is_reserved_edges(db=db, node_id=detached["id"], attribute_name="sequence")
        assert (closed.status, closed.is_open) == ("active", False), "the IS_RESERVED edge is ended, not deleted"
        assert await tracking_pool_id(db=db, node_id=detached["id"], attribute_name="sequence") is None
        following = await create_ticket(
            db=db,
            branch=main_branch,
            title="detach-next",
            ticket_id={"value": 1292},
            sequence={"from_pool": {"id": pool.id}},
        )
        assert following["sequence"]["value"] == 1200, "the detached number is offered again"

    async def test_detaching_one_holder_of_a_duplicate_leaves_the_other_reported(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(
            db=db, name="detach-duplicate", start_range=1300, end_range=1309, node_attribute="sequence"
        )
        first = await create_ticket(
            db=db,
            branch=main_branch,
            title="detach-duplicate-first",
            ticket_id={"value": 1390},
            sequence={"value": 1300, "from_pool": {"id": pool.id}},
        )
        second = await create_ticket(
            db=db,
            branch=main_branch,
            title="detach-duplicate-second",
            ticket_id={"value": 1391},
            sequence={"value": 1300, "from_pool": {"id": pool.id}},
        )
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [1300, 1300]

        await update_ticket(db=db, branch=main_branch, node_id=first["id"], sequence={"from_pool": None})

        assert await open_is_reserved_edges(db=db, pool=pool) == {(second["id"], "provided")}
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [(second["id"], "main", 1300)]
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [1300]
        following = await create_ticket(
            db=db,
            branch=main_branch,
            title="detach-duplicate-next",
            ticket_id={"value": 1392},
            sequence={"from_pool": {"id": pool.id}},
        )
        assert following["sequence"]["value"] == 1301, "the other holder still keeps 1300 taken"

    @pytest.mark.parametrize(
        "case",
        [
            ReattachCase(
                name="held-value",
                start_range=1500,
                reattach_payload={"value": 1505},
                expected_value=1505,
                expected_provenance="provided",
            ),
            ReattachCase(
                name="null-value",
                start_range=1600,
                reattach_payload={"value": None},
                expected_value=1600,
                expected_provenance="allocated",
            ),
        ],
        ids=lambda case: case.name,
    )
    async def test_a_detached_number_can_be_tracked_again_by_the_same_pool(
        self, db: InfrahubDatabase, main_branch: Branch, case: ReattachCase
    ) -> None:
        pool = await new_pool(
            db=db, name=f"reattach-{case.name}", start_range=case.start_range, end_range=case.start_range + 9
        )
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title=f"reattach-{case.name}",
            ticket_id={"value": case.start_range + 5, "from_pool": {"id": pool.id}},
        )
        await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"from_pool": None})
        [ended] = await is_reserved_edges(db=db, node_id=ticket["id"])
        assert (ended.status, ended.is_open) == ("active", False)
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == []

        changed = await update_ticket(
            db=db,
            branch=main_branch,
            node_id=ticket["id"],
            ticket_id={**case.reattach_payload, "from_pool": {"id": pool.id}},
        )

        assert changed["ticket_id"]["value"] == case.expected_value
        edges = await is_reserved_edges(db=db, node_id=ticket["id"])
        assert sorted((edge.status, edge.is_open) for edge in edges) == [("active", False), ("active", True)]
        assert ended in edges, "the ended IS_RESERVED edge stays ended"
        assert await open_is_reserved_edges(db=db, pool=pool) == {(ticket["id"], case.expected_provenance)}
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == [
            (ticket["id"], "main", case.expected_value)
        ]
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == pool.get_id()
        sources = await pooled_sources(db=db, branch=main_branch, node_id=ticket["id"])
        assert sources["ticket_id"] == (case.expected_value, pool.get_id())

    async def test_a_detach_on_a_deleted_branch_stays_in_effect_on_every_branch(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="detach-branch", start_range=1400, end_range=1409)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="detach-branch", ticket_id={"from_pool": {"id": pool.id}}
        )
        assert ticket["ticket_id"]["value"] == 1400
        other_branch = await create_branch(branch_name="detach-branch-other", db=db)
        detaching_branch = await create_branch(branch_name="detach-branch-detaching", db=db)

        await update_ticket(db=db, branch=detaching_branch, node_id=ticket["id"], ticket_id={"from_pool": None})
        await BranchDataDeleter(db=db, batch_size=5).delete(branch=detaching_branch)

        for branch in (main_branch, other_branch):
            sources = await pooled_sources(db=db, branch=branch, node_id=ticket["id"])
            assert sources["ticket_id"] == (1400, None), f"{branch.name} reports a pool source"
        assert await open_is_reserved_edges(db=db, pool=pool) == set()
        assert await allocated_rows(db=db, branch=main_branch, pool=pool) == []
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == []

    async def test_deleting_a_pool_ends_its_records_and_leaves_the_numbers(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="delete-pool", start_range=1700, end_range=1709)
        successor = await new_pool(db=db, name="delete-pool-successor", start_range=1700, end_range=1719)
        first = await create_ticket(
            db=db, branch=main_branch, title="delete-pool-first", ticket_id={"from_pool": {"id": pool.id}}
        )
        second = await create_ticket(
            db=db, branch=main_branch, title="delete-pool-second", ticket_id={"from_pool": {"id": pool.id}}
        )
        provided = await create_ticket(
            db=db,
            branch=main_branch,
            title="delete-pool-provided",
            ticket_id={"value": 1705, "from_pool": {"id": pool.id}},
        )
        other_branch = await create_branch(branch_name="delete-pool-other", db=db)
        assert await open_is_reserved_edges(db=db, pool=pool) == {
            (first["id"], "allocated"),
            (second["id"], "allocated"),
            (provided["id"], "provided"),
        }

        await execute(db=db, branch=main_branch, source=DELETE_POOL, variables={"id": pool.id})

        assert await NodeManager.get_one(db=db, id=pool.id, branch=main_branch) is None
        assert await open_is_reserved_edges(db=db, pool=pool) == set()
        for ticket, value in ((first, 1700), (second, 1701), (provided, 1705)):
            [ended] = await is_reserved_edges(db=db, node_id=ticket["id"])
            assert (ended.status, ended.is_open) == ("active", False), "the IS_RESERVED edge is ended, not deleted"
            assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None
            for branch in (main_branch, other_branch):
                sources = await pooled_sources(db=db, branch=branch, node_id=ticket["id"])
                assert sources["ticket_id"] == (value, None), f"{branch.name} lost the number or reports a pool"

        for ticket, value in ((first, 1700), (second, 1701), (provided, 1705)):
            changed = await update_ticket(
                db=db,
                branch=main_branch,
                node_id=ticket["id"],
                ticket_id={"value": value, "from_pool": {"id": successor.id}},
            )
            assert changed["ticket_id"]["value"] == value
        assert await open_is_reserved_edges(db=db, pool=successor) == {
            (first["id"], "provided"),
            (second["id"], "provided"),
            (provided["id"], "provided"),
        }
        assert await used_numbers(db=db, branch=main_branch, pool=successor) == [1700, 1701, 1705]

    async def test_pool_writes_record_the_acting_account_on_the_record_and_the_pool(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """Drawing, releasing and attaching each run as a different account, and each leaves that account behind."""
        pool = await new_pool(db=db, name="actor", start_range=1800, end_range=1809, node_attribute="sequence")

        drawn = await create_ticket(
            db=db,
            branch=main_branch,
            title="actor-drawn",
            account_session=session_for(TEST_ACTOR_ID),
            ticket_id={"value": 1890},
            sequence={"from_pool": {"id": pool.id}},
        )

        [opened] = await is_reserved_edges(db=db, node_id=drawn["id"], attribute_name="sequence")
        assert (opened.from_user_id, opened.to_user_id) == (TEST_ACTOR_ID, None)
        after_draw = await node_metadata(db=db, node_id=pool.get_id())
        assert (after_draw.updated_at, after_draw.updated_by) == (opened.from_time, TEST_ACTOR_ID)

        await update_ticket(
            db=db,
            branch=main_branch,
            node_id=drawn["id"],
            account_session=session_for(SECOND_ACTOR_ID),
            sequence={"from_pool": None},
        )

        [released] = await is_reserved_edges(db=db, node_id=drawn["id"], attribute_name="sequence")
        assert (released.from_user_id, released.is_open, released.to_user_id) == (TEST_ACTOR_ID, False, SECOND_ACTOR_ID)
        after_release = await node_metadata(db=db, node_id=pool.get_id())
        assert (
            after_release.updated_at,
            after_release.updated_by,
            after_release.previous_updated_at,
            after_release.previous_updated_by,
        ) == (released.to_time, SECOND_ACTOR_ID, opened.from_time, TEST_ACTOR_ID)

        hand_set = await create_ticket(
            db=db,
            branch=main_branch,
            title="actor-hand-set",
            account_session=session_for(TEST_ACTOR_ID),
            ticket_id={"value": 1891},
            sequence={"value": 1805},
        )
        await update_ticket(
            db=db,
            branch=main_branch,
            node_id=hand_set["id"],
            account_session=session_for(THIRD_ACTOR_ID),
            sequence={"value": 1805, "from_pool": {"id": pool.id}},
        )

        [attached] = await is_reserved_edges(db=db, node_id=hand_set["id"], attribute_name="sequence")
        assert (attached.from_user_id, attached.to_user_id) == (THIRD_ACTOR_ID, None)
        after_attach = await node_metadata(db=db, node_id=pool.get_id())
        assert (after_attach.updated_at, after_attach.updated_by) == (attached.from_time, THIRD_ACTOR_ID)

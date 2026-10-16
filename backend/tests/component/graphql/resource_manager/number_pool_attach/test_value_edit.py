"""Writes that change a number a pool tracks without naming a pool, through the GraphQL mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager

from .helpers import (
    UPDATE_TICKET,
    create_ticket,
    is_reserved_edges,
    new_pool,
    refused_write,
    tracking_pool_id,
    update_ticket,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
    from infrahub.database import InfrahubDatabase

UPDATE_TICKET_DATA = """
mutation UpdateTicket($data: TestingTicketUpdateInput!) {
    TestingTicketUpdate(data: $data) { ok }
}
"""

UPSERT_TICKET_DATA = """
mutation UpsertTicket($data: TestingTicketUpsertInput!) {
    TestingTicketUpsert(data: $data) { ok }
}
"""


def _tracked_edit_message(pool_name: str, value: int, ranges: str, key: str = "ticket_id.value") -> str:
    attribute_name = key.split(".", maxsplit=1)[0]
    return (
        f"'{attribute_name}' is tracked by the {pool_name} pool, so it cannot hold {value}, which is outside the "
        f"pool's ranges: {ranges}. To set {value} and stop the pool tracking '{attribute_name}', send "
        f"'value: {value}' together with 'from_pool: null'. at {key}"
    )


async def _held_value(db: InfrahubDatabase, branch: Branch, node_id: str, attribute_name: str = "ticket_id") -> Any:
    ticket = await NodeManager.get_one(db=db, id=node_id, branch=branch)
    assert ticket is not None
    return ticket.get_attribute(name=attribute_name).value


@dataclass(frozen=True)
class UntrackedEditCase:
    name: str
    held: int
    """A number no pool tracks."""
    value: int | None


UNTRACKED_EDIT_CASES = [
    UntrackedEditCase(name="any_number", held=7081, value=7990),
    UntrackedEditCase(name="null", held=7082, value=None),
]


@dataclass(frozen=True)
class GetterCase:
    name: str
    source: str
    data: dict[str, Any]
    """The mutation payload; `ID`, `TITLE` and `TICKET_ID` stand for the existing ticket's id, title and number."""


GETTER_CASES = [
    GetterCase(name="update_by_id", source=UPDATE_TICKET_DATA, data={"id": "ID"}),
    GetterCase(name="update_by_hfid", source=UPDATE_TICKET_DATA, data={"hfid": ["TITLE", "TICKET_ID"]}),
    GetterCase(name="update_by_default_filter", source=UPDATE_TICKET_DATA, data={"id": "TITLE"}),
    GetterCase(name="upsert_by_id", source=UPSERT_TICKET_DATA, data={"id": "ID"}),
    GetterCase(name="upsert_by_hfid", source=UPSERT_TICKET_DATA, data={"hfid": ["TITLE", "TICKET_ID"]}),
    GetterCase(
        name="upsert_by_the_hfid_values_of_a_create_payload",
        source=UPSERT_TICKET_DATA,
        data={"title": {"value": "TITLE"}, "ticket_id": {"value": "TICKET_ID"}},
    ),
]


def _fill(payload: Any, node_id: str, title: str, ticket_id: int) -> Any:
    """Replace the placeholders in a payload; the number is a string inside an `hfid` and a number elsewhere."""
    if isinstance(payload, dict):
        return {
            key: _fill(payload=value, node_id=node_id, title=title, ticket_id=ticket_id)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [str(_fill(payload=item, node_id=node_id, title=title, ticket_id=ticket_id)) for item in payload]
    return (
        {"ID": node_id, "TITLE": title, "TICKET_ID": ticket_id}.get(payload, payload)
        if isinstance(payload, str)
        else payload
    )


class TestNumberPoolValueEdit:
    """Value-only edits of a tracked number are checked against the ranges of the pool tracking it.

    The schema and the two pools are loaded once for the class, and tickets accumulate across tests, so every test
    holds numbers of its own.
    """

    @pytest.fixture(scope="class")
    async def ticket_pool(self, db: InfrahubDatabase, main_branch: Branch) -> CoreNumberPool:
        return await new_pool(db=db, name="value-edit", start_range=7000, end_range=7699)

    @pytest.fixture(scope="class")
    async def sequence_pool(self, db: InfrahubDatabase, main_branch: Branch) -> CoreNumberPool:
        return await new_pool(
            db=db, name="value-edit-sequence", start_range=7000, end_range=7699, node_attribute="sequence"
        )

    async def test_moving_a_tracked_number_outside_the_range_is_refused(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-refused",
            ticket_id={"value": 7005, "from_pool": {"id": ticket_pool.id}},
        )
        before = await is_reserved_edges(db=db, node_id=ticket["id"])

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 7900}},
        )

        assert message == _tracked_edit_message(pool_name="value-edit", value=7900, ranges="7000-7699")
        assert await _held_value(db=db, branch=main_branch, node_id=ticket["id"]) == 7005
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before

    async def test_moving_a_tracked_number_outside_the_range_with_a_null_pool_detaches_it(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-detach",
            ticket_id={"value": 7015, "from_pool": {"id": ticket_pool.id}},
        )

        changed = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 7910, "from_pool": None}
        )

        assert changed["ticket_id"]["value"] == 7910
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None

    async def test_moving_a_tracked_number_inside_the_range_keeps_it_tracked(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-inside",
            ticket_id={"value": 7025, "from_pool": {"id": ticket_pool.id}},
        )

        changed = await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 7026})

        assert changed["ticket_id"]["value"] == 7026
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == ticket_pool.get_id()

    async def test_restating_the_tracking_pool_with_a_number_outside_the_range_is_refused(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-same-pool",
            ticket_id={"value": 7035, "from_pool": {"id": ticket_pool.id}},
        )
        before = await is_reserved_edges(db=db, node_id=ticket["id"])

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 7930, "from_pool": {"id": ticket_pool.id}}},
        )

        assert message == _tracked_edit_message(
            pool_name="value-edit", value=7930, ranges="7000-7699", key="ticket_id.from_pool"
        )
        assert await _held_value(db=db, branch=main_branch, node_id=ticket["id"]) == 7035
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before

    async def test_restating_the_tracked_number_changes_nothing(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-restate",
            ticket_id={"value": 7045, "from_pool": {"id": ticket_pool.id}},
        )
        before = await is_reserved_edges(db=db, node_id=ticket["id"])

        changed = await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 7045})

        assert changed["ticket_id"]["value"] == 7045
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before

    async def test_moving_a_number_tracked_on_main_outside_the_range_on_a_branch_is_refused(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-on-branch",
            ticket_id={"value": 7055, "from_pool": {"id": ticket_pool.id}},
        )
        branch = await create_branch(branch_name="edit-on-branch", db=db)
        before = await is_reserved_edges(db=db, node_id=ticket["id"])

        message = await refused_write(
            db=db,
            branch=branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 7950}},
        )

        assert message == _tracked_edit_message(pool_name="value-edit", value=7950, ranges="7000-7699")
        assert await _held_value(db=db, branch=branch, node_id=ticket["id"]) == 7055
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before

    async def test_emptying_a_tracked_number_is_refused(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-empty",
            ticket_id={"value": 7065, "from_pool": {"id": ticket_pool.id}},
        )
        before = await is_reserved_edges(db=db, node_id=ticket["id"])

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": None}},
        )

        assert message == (
            "'ticket_id' is tracked by the value-edit pool, so it cannot be emptied. To empty 'ticket_id' and stop "
            "the pool tracking it, send 'value: null' together with 'from_pool: null'. at ticket_id.value"
        )
        assert await _held_value(db=db, branch=main_branch, node_id=ticket["id"]) == 7065
        assert await is_reserved_edges(db=db, node_id=ticket["id"]) == before

    async def test_emptying_a_tracked_number_with_a_null_pool_detaches_it(
        self, db: InfrahubDatabase, main_branch: Branch, ticket_pool: CoreNumberPool
    ) -> None:
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-empty-detach",
            ticket_id={"value": 7075, "from_pool": {"id": ticket_pool.id}},
        )

        changed = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": None, "from_pool": None}
        )

        assert changed["ticket_id"]["value"] is None
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None

    @pytest.mark.usefixtures("sequence_pool")
    @pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in UNTRACKED_EDIT_CASES])
    async def test_a_number_no_pool_tracks_takes_any_value(
        self, db: InfrahubDatabase, main_branch: Branch, test_case: UntrackedEditCase
    ) -> None:
        """A pool exists for `sequence` but does not track this ticket's number, so any number is accepted."""
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title=f"edit-untracked-{test_case.name}",
            ticket_id={"value": test_case.held},
            sequence={"value": test_case.held},
        )

        changed = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], sequence={"value": test_case.value}
        )

        assert changed["sequence"]["value"] == test_case.value
        assert await tracking_pool_id(db=db, node_id=ticket["id"], attribute_name="sequence") is None

    @pytest.fixture(scope="class")
    async def sequence_tracked_ticket(
        self, db: InfrahubDatabase, main_branch: Branch, sequence_pool: CoreNumberPool
    ) -> dict[str, Any]:
        """Every mutation path is refused, so one ticket serves them all."""
        return await create_ticket(
            db=db,
            branch=main_branch,
            title="edit-every-path",
            ticket_id={"value": 7600},
            sequence={"value": 7600, "from_pool": {"id": sequence_pool.id}},
        )

    @pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in GETTER_CASES])
    async def test_every_mutation_that_finds_the_object_checks_the_tracked_number(
        self, db: InfrahubDatabase, main_branch: Branch, sequence_tracked_ticket: dict[str, Any], test_case: GetterCase
    ) -> None:
        ticket = sequence_tracked_ticket
        data = _fill(payload=test_case.data, node_id=ticket["id"], title="edit-every-path", ticket_id=7600)
        data["sequence"] = {"value": 7999}

        message = await refused_write(db=db, branch=main_branch, source=test_case.source, variables={"data": data})

        assert message == _tracked_edit_message(
            pool_name="value-edit-sequence", value=7999, ranges="7000-7699", key="sequence.value"
        )
        assert await _held_value(db=db, branch=main_branch, node_id=ticket["id"], attribute_name="sequence") == 7600

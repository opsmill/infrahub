"""An upsert that updates a tracked number reports its pool as `source`, whichever way it finds the node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from .helpers import attribute_read, create_ticket, execute, new_pool, pool_source

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

UPSERT_TICKET = """
mutation UpsertTicket($data: TestingTicketUpsertInput!) {
    TestingTicketUpsert(data: $data) {
        ok
        object { id ticket_id { value source { id __typename } } sequence { value } }
    }
}
"""


@dataclass(frozen=True)
class UpsertLookupCase:
    name: str
    start_range: int
    """Tickets accumulate across the class, so each case draws from a range of its own."""
    data: dict[str, Any]
    """The upsert payload; `TITLE` and `TICKET_ID` stand for the existing ticket's title and number."""


UPSERT_LOOKUP_CASES = [
    UpsertLookupCase(
        name="by_the_hfid_field",
        start_range=700,
        data={"hfid": ["TITLE", "TICKET_ID"], "sequence": {"value": 7}},
    ),
    UpsertLookupCase(
        name="by_the_hfid_values_of_a_create_payload",
        start_range=710,
        data={"title": {"value": "TITLE"}, "ticket_id": {"value": "TICKET_ID"}, "sequence": {"value": 7}},
    ),
]


def fill(payload: Any, title: str, ticket_id: int) -> Any:
    """Replace the placeholders in a payload; the number is a string inside an `hfid` and a number elsewhere."""
    if isinstance(payload, dict):
        return {
            key: [title if item == "TITLE" else str(ticket_id) for item in value]
            if key == "hfid"
            else fill(payload=value, title=title, ticket_id=ticket_id)
            for key, value in payload.items()
        }
    if payload == "TITLE":
        return title
    if payload == "TICKET_ID":
        return ticket_id
    return payload


class TestNumberPoolUpsert:
    @pytest.mark.parametrize("test_case", [pytest.param(case, id=case.name) for case in UPSERT_LOOKUP_CASES])
    async def test_an_upsert_of_a_tracked_number_reports_its_pool(
        self, db: InfrahubDatabase, main_branch: Branch, test_case: UpsertLookupCase
    ) -> None:
        pool = await new_pool(
            db=db,
            name=f"upsert-{test_case.name}",
            start_range=test_case.start_range,
            end_range=test_case.start_range + 9,
        )
        title = f"upsert-{test_case.name}"
        ticket = await create_ticket(db=db, branch=main_branch, title=title, ticket_id={"from_pool": {"id": pool.id}})
        ticket_id = ticket["ticket_id"]["value"]
        assert ticket_id == test_case.start_range

        data = fill(payload=test_case.data, title=title, ticket_id=ticket_id)
        response = await execute(db=db, branch=main_branch, source=UPSERT_TICKET, variables={"data": data})
        assert response
        upserted = response["TestingTicketUpsert"]["object"]

        assert upserted["id"] == ticket["id"], "the upsert updated the existing ticket"
        assert upserted["sequence"]["value"] == 7
        assert attribute_read(upserted["ticket_id"]) == pool_source(value=ticket_id, pool=pool)

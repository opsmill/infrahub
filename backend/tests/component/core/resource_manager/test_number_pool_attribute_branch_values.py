"""The number each live branch holds for an attribute, one row per attribute and branch.

A pool's record covers an attribute on every branch, so an attach reads what every live branch holds. A branch
holds the value of its own edge, or the default branch's value it inherits: the open one when it forked after
that value was written, or the closed one it still reads at its fork point.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.pools.number_pool_attribute_branch_values import NumberPoolAttributeBranchValues
from infrahub.pools.range_refusal import BranchValue
from tests.component.core.resource_manager.conftest import delete_branch
from tests.helpers.schema import TICKET, load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _agnostic_ticket_schema() -> NodeSchema:
    """A ticket whose number every branch shares, stored once on the global branch."""
    schema = deepcopy(TICKET)
    schema.name = "AgnosticTicket"
    schema.get_attribute(name="ticket_id").branch = BranchSupportType.AGNOSTIC
    return schema


AGNOSTIC_TICKET = _agnostic_ticket_schema()


@pytest.fixture(scope="class")
async def ticket_schema(
    db: InfrahubDatabase,
    default_branch_scope_class: Branch,
    register_core_models_schema_scope_class: SchemaBranch,
) -> Branch:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET, AGNOSTIC_TICKET]))
    await initialize_registry(db=db)
    return default_branch_scope_class


async def _new_ticket(
    db: InfrahubDatabase, title: str, ticket_id: int | None, schema: NodeSchema = TICKET
) -> tuple[Node, str]:
    ticket = await Node.init(db=db, schema=schema.kind)
    await ticket.new(db=db, title=title, ticket_id=ticket_id)
    await ticket.save(db=db)
    attribute_id = ticket.get_attribute("ticket_id").id
    assert attribute_id is not None
    return ticket, attribute_id


async def _set_on_branch(db: InfrahubDatabase, ticket: Node, branch: Branch, ticket_id: int | None) -> None:
    on_branch = await NodeManager.get_one(db=db, id=ticket.id, branch=branch, raise_on_error=True)
    on_branch.get_attribute("ticket_id").value = ticket_id
    await on_branch.save(db=db)


async def _read(db: InfrahubDatabase, attribute_ids: list[str]) -> list[BranchValue]:
    return await NumberPoolAttributeBranchValues(db=db).read(attribute_ids=attribute_ids)


class TestAttributeBranchValues:
    """The schema is loaded once; every test uses its own tickets and branches, and reads only its own attributes."""

    async def test_a_value_only_the_default_branch_holds_reads_once(
        self, db: InfrahubDatabase, ticket_schema: Branch
    ) -> None:
        _, attribute_id = await _new_ticket(db=db, title="main-only", ticket_id=101)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=101)
        ]

    async def test_a_branch_agnostic_value_reads_once_under_the_global_branch(
        self, db: InfrahubDatabase, ticket_schema: Branch
    ) -> None:
        ticket, attribute_id = await _new_ticket(
            db=db, title="shared-by-every-branch", ticket_id=601, schema=AGNOSTIC_TICKET
        )
        branch = await create_branch(branch_name="changes-the-shared-value", db=db)
        await _set_on_branch(db=db, ticket=ticket, branch=branch, ticket_id=602)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=GLOBAL_BRANCH_NAME, value=602)
        ]

    async def test_a_branch_inheriting_the_open_default_value_reads_it_under_its_own_name(
        self, db: InfrahubDatabase, ticket_schema: Branch
    ) -> None:
        _, attribute_id = await _new_ticket(db=db, title="inherited", ticket_id=201)
        branch = await create_branch(branch_name="inherits-the-open-value", db=db)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=branch.name, value=201),
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=201),
        ]

    async def test_a_branch_with_its_own_value_reads_only_that_value(
        self, db: InfrahubDatabase, ticket_schema: Branch
    ) -> None:
        ticket, attribute_id = await _new_ticket(db=db, title="own-value", ticket_id=301)
        branch = await create_branch(branch_name="writes-its-own-value", db=db)
        await _set_on_branch(db=db, ticket=ticket, branch=branch, ticket_id=302)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=301),
            BranchValue(attribute_id=attribute_id, branch=branch.name, value=302),
        ]

    async def test_an_older_branch_reads_the_default_value_closed_after_its_fork_point(
        self, db: InfrahubDatabase, ticket_schema: Branch
    ) -> None:
        ticket, attribute_id = await _new_ticket(db=db, title="closed-on-main", ticket_id=401)
        older = await create_branch(branch_name="predates-the-change-on-main", db=db)
        ticket.get_attribute("ticket_id").value = 402
        await ticket.save(db=db)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=402),
            BranchValue(attribute_id=attribute_id, branch=older.name, value=401),
        ]

    async def test_one_read_reports_every_attribute_it_names(self, db: InfrahubDatabase, ticket_schema: Branch) -> None:
        first, first_id = await _new_ticket(db=db, title="several-first", ticket_id=501)
        _, second_id = await _new_ticket(db=db, title="several-second", ticket_id=502)
        branch = await create_branch(branch_name="reads-several", db=db)
        await _set_on_branch(db=db, ticket=first, branch=branch, ticket_id=503)

        rows = await _read(db=db, attribute_ids=[first_id, second_id])

        assert sorted(rows, key=lambda row: (row.value, row.branch)) == [
            BranchValue(attribute_id=first_id, branch=ticket_schema.name, value=501),
            BranchValue(attribute_id=second_id, branch=ticket_schema.name, value=502),
            BranchValue(attribute_id=second_id, branch=branch.name, value=502),
            BranchValue(attribute_id=first_id, branch=branch.name, value=503),
        ]

    async def test_a_branch_being_deleted_holds_nothing(self, db: InfrahubDatabase, ticket_schema: Branch) -> None:
        ticket, attribute_id = await _new_ticket(db=db, title="branch-being-deleted", ticket_id=601)
        own_value = await create_branch(branch_name="deleting-with-its-own-value", db=db)
        await _set_on_branch(db=db, ticket=ticket, branch=own_value, ticket_id=602)
        inheriting = await create_branch(branch_name="deleting-while-inheriting", db=db)

        await db.execute_query(
            query='MATCH (b:Branch) WHERE b.name IN $names SET b.status = "DELETING"',
            params={"names": [own_value.name, inheriting.name]},
        )

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=601)
        ]

    async def test_a_deleted_branch_holds_nothing(self, db: InfrahubDatabase, ticket_schema: Branch) -> None:
        ticket, attribute_id = await _new_ticket(db=db, title="branch-deleted", ticket_id=701)
        branch = await create_branch(branch_name="deleted-with-its-own-value", db=db)
        await _set_on_branch(db=db, ticket=ticket, branch=branch, ticket_id=702)

        await delete_branch(db=db, branch=branch)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=701)
        ]

    async def test_a_branch_that_deleted_the_object_holds_nothing(
        self, db: InfrahubDatabase, ticket_schema: Branch
    ) -> None:
        ticket, attribute_id = await _new_ticket(db=db, title="deleted-on-a-branch", ticket_id=751)
        branch = await create_branch(branch_name="deletes-the-object", db=db)
        on_branch = await NodeManager.get_one(db=db, id=ticket.id, branch=branch, raise_on_error=True)
        await on_branch.delete(db=db)

        assert await _read(db=db, attribute_ids=[attribute_id]) == [
            BranchValue(attribute_id=attribute_id, branch=ticket_schema.name, value=751)
        ]

    async def test_a_branch_holding_no_number_holds_nothing(self, db: InfrahubDatabase, ticket_schema: Branch) -> None:
        _, never_set_id = await _new_ticket(db=db, title="never-set", ticket_id=None)
        emptied, emptied_id = await _new_ticket(db=db, title="emptied-on-a-branch", ticket_id=801)
        branch = await create_branch(branch_name="empties-the-number", db=db)
        await _set_on_branch(db=db, ticket=emptied, branch=branch, ticket_id=None)

        assert await _read(db=db, attribute_ids=[never_set_id, emptied_id]) == [
            BranchValue(attribute_id=emptied_id, branch=ticket_schema.name, value=801)
        ]

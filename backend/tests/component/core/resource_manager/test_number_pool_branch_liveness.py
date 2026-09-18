"""A number is free only when no branch still holds it.

A number pool reports its used and free numbers from the reservation ledger. Because an attribute is
branch-aware, the same attribute can carry a different value on every branch. The pool must therefore
read liveness as a union across branches: a number stays taken while *any* branch still holds it, and
becomes allocatable only once *every* branch has let it go.
"""

from copy import deepcopy

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.schema import TICKET, load_schema

POOL_START = 1
POOL_END = 10


async def _make_pool(db: InfrahubDatabase) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema="CoreNumberPool")
    await pool.new(
        db=db,
        name="pool1",
        node=TICKET.kind,
        node_attribute="ticket_id",
        start_range=POOL_START,
        end_range=POOL_END,
    )
    await pool.save(db=db)
    return pool


async def _new_ticket(db: InfrahubDatabase, pool: CoreNumberPool, title: str) -> Node:
    ticket = await Node.init(db=db, schema=TICKET.kind)
    await ticket.new(db=db, title=title, ticket_id={"from_pool": {"id": pool.id}})
    await ticket.save(db=db)
    return ticket


class TestBranchLiveness:
    """The pool and its schema are built once; each test adds to the state the one before it left."""

    @pytest.fixture(scope="class")
    async def pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> CoreNumberPool:
        await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
        await initialize_registry(db=db)
        return await _make_pool(db=db)

    async def test_a_number_changed_on_a_branch_is_still_held_by_the_default_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        """Moving the value on a branch must not free the number the default branch still holds."""
        ticket = await _new_ticket(db=db, pool=pool, title="moved-on-a-branch")
        held = ticket.get_attribute("ticket_id").value
        assert await pool.get_used(db=db, branch=default_branch_scope_class) == [held]
        free_before = await pool.get_free(db=db, branch=default_branch_scope_class)

        branch = await create_branch(branch_name="liveness-value-change", db=db)
        on_branch = await NodeManager.get_one(db=db, id=ticket.id, branch=branch, raise_on_error=True)
        on_branch.get_attribute("ticket_id").value = POOL_END
        await on_branch.save(db=db)

        assert await pool.get_used(db=db, branch=default_branch_scope_class) == [held, POOL_END], (
            "the default branch still holds its number and the branch now holds another"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) == free_before, (
            "moving the value on a branch changes nothing the default branch can be offered"
        )

    async def test_an_object_deleted_on_a_branch_is_still_held_by_the_default_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        """Deleting the object on a branch must not free the number the default branch still holds."""
        ticket = await _new_ticket(db=db, pool=pool, title="deleted-on-a-branch")
        held = ticket.get_attribute("ticket_id").value
        used_before = await pool.get_used(db=db, branch=default_branch_scope_class)

        branch = await create_branch(branch_name="liveness-object-delete", db=db)
        on_branch = await NodeManager.get_one(db=db, id=ticket.id, branch=branch, raise_on_error=True)
        await on_branch.delete(db=db)

        assert await pool.get_used(db=db, branch=default_branch_scope_class) == used_before, (
            f"deleting the object on a branch freed ticket_id={held} the default branch still holds"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) != held

    async def test_a_number_another_branch_holds_is_never_allocated(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        """A number released only on a branch must never be handed to a new object on the default branch."""
        keeper = await _new_ticket(db=db, pool=pool, title="keeper")
        branch = await create_branch(branch_name="liveness-never-reallocated", db=db)
        on_branch = await NodeManager.get_one(db=db, id=keeper.id, branch=branch, raise_on_error=True)
        await on_branch.delete(db=db)

        intruder = await _new_ticket(db=db, pool=pool, title="intruder")

        still_there = await NodeManager.get_one(
            db=db, id=keeper.id, branch=default_branch_scope_class, raise_on_error=True
        )
        held = still_there.get_attribute("ticket_id").value
        assert intruder.get_attribute("ticket_id").value != held, (
            f"the pool allocated ticket_id={held}, which the default branch still holds"
        )


async def test_a_held_number_is_never_allocated_when_the_attribute_is_not_unique(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Without a uniqueness constraint to fall back on, the pool alone must keep the number taken.

    Stands apart from `TestBranchLiveness` because it needs the attribute without its uniqueness
    constraint, and the class loads the schema once for every test in it.
    """
    schema = deepcopy(TICKET)
    next(attribute for attribute in schema.attributes if attribute.name == "ticket_id").unique = False
    await load_schema(db=db, schema=SchemaRoot(nodes=[schema]))
    await initialize_registry(db=db)

    pool = await _make_pool(db=db)
    keeper = await _new_ticket(db=db, pool=pool, title="keeper")

    branch = await create_branch(branch_name="liveness-not-unique", db=db)
    on_branch = await NodeManager.get_one(db=db, id=keeper.id, branch=branch, raise_on_error=True)
    await on_branch.delete(db=db)

    intruder = await _new_ticket(db=db, pool=pool, title="intruder")

    still_there = await NodeManager.get_one(db=db, id=keeper.id, branch=default_branch, raise_on_error=True)
    held = still_there.get_attribute("ticket_id").value
    assert intruder.get_attribute("ticket_id").value != held, (
        f"the pool allocated ticket_id={held}, which the default branch still holds"
    )

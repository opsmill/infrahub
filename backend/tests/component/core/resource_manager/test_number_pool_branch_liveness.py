"""A number is free only when no branch still holds it.

A number pool reports its used and free numbers from the reservation ledger. Because an attribute is
branch-aware, the same attribute can carry a different value on every branch. The pool must therefore
read liveness as a union across branches: a number stays taken while *any* branch still holds it, and
becomes allocatable only once *every* branch has let it go.
"""

from copy import deepcopy

import pytest

from infrahub.core.branch import Branch
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.initialization import create_branch, initialize_registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from tests.helpers.agnostic_edges import TEST_ACTOR_ID
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
        assert isinstance(held, int)

        branch = await create_branch(branch_name="liveness-value-change", db=db)
        on_branch = await NodeManager.get_one(db=db, id=ticket.id, branch=branch, raise_on_error=True)
        moved_to = held + 1
        on_branch.get_attribute("ticket_id").value = moved_to
        await on_branch.save(db=db)

        assert await pool.get_used(db=db, branch=default_branch_scope_class) == [held, moved_to], (
            "the default branch still holds its number and the branch now holds another"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) not in [held, moved_to], (
            "neither the default branch's number nor the one the branch moved to may be offered"
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

    async def test_a_number_every_branch_has_released_is_free_again(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        """The other half of the union: once no branch holds the number any more, the pool offers it."""
        ticket = await _new_ticket(db=db, pool=pool, title="released-everywhere")
        assert ticket.get_attribute("ticket_id").value == 6, "the tests before this one hold 1 through 5"
        assert await pool.get_used(db=db, branch=default_branch_scope_class) == [1, 2, 3, 4, 5, 6]

        branch = await create_branch(branch_name="liveness-released-everywhere", db=db)
        on_branch = await NodeManager.get_one(db=db, id=ticket.id, branch=branch, raise_on_error=True)
        await on_branch.delete(db=db)
        assert await pool.get_used(db=db, branch=default_branch_scope_class) == [1, 2, 3, 4, 5, 6], (
            "one branch letting go is not every branch letting go"
        )

        await ticket.delete(db=db)

        assert await pool.get_used(db=db, branch=default_branch_scope_class) == [1, 2, 3, 4, 5], (
            "with no branch holding it, the number stops counting as used"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) == 6, (
            "and the pool offers it again rather than skipping past it"
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


class TestOlderBranchLiveness:
    """A branch created before a change on the default branch still holds what the default branch let go.

    The default branch closes its own value edge when it deletes the object or moves the number, but a
    branch that forked earlier still reads that edge at its fork point. The pool and its schema are
    built once, and every older branch a test creates outlives it, so each test asserts on the numbers
    it allocated rather than on the whole used set. Every number below the one a test frees is still
    held by an earlier test's older branch, so the freed number is the lowest free one.
    """

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

    async def test_an_object_deleted_on_the_default_branch_is_still_held_by_an_older_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        ticket = await _new_ticket(db=db, pool=pool, title="deleted-on-the-default-branch")
        held = ticket.get_attribute("ticket_id").value
        older = await create_branch(branch_name="predates-the-delete", db=db)

        await ticket.delete(db=db)

        assert await NodeManager.get_one(db=db, id=ticket.id, branch=older) is not None
        assert held in await pool.get_used(db=db, branch=default_branch_scope_class), (
            "the older branch still holds the object, so its number stays used"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) != held, (
            "a number an older branch still holds must never be offered again"
        )

    async def test_a_number_changed_on_the_default_branch_is_still_held_by_an_older_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        ticket = await _new_ticket(db=db, pool=pool, title="moved-on-the-default-branch")
        held = ticket.get_attribute("ticket_id").value
        older = await create_branch(branch_name="predates-the-change", db=db)

        moved_to = held + 1
        ticket.get_attribute("ticket_id").value = moved_to
        await ticket.save(db=db)

        on_older = await NodeManager.get_one(db=db, id=ticket.id, branch=older, raise_on_error=True)
        assert on_older.get_attribute("ticket_id").value == held
        used = await pool.get_used(db=db, branch=default_branch_scope_class)
        assert {held, moved_to} <= set(used), (
            "the default branch now holds the new number and the older branch still holds the old one"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) != held

    async def test_rebasing_the_older_branch_past_the_delete_frees_the_number(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        ticket = await _new_ticket(db=db, pool=pool, title="freed-by-a-rebase")
        held = ticket.get_attribute("ticket_id").value
        older = await create_branch(branch_name="rebased-past-the-delete", db=db)
        await ticket.delete(db=db)
        assert held in await pool.get_used(db=db, branch=default_branch_scope_class)

        await older.rebase(db=db)

        assert held not in await pool.get_used(db=db, branch=default_branch_scope_class), (
            "once the older branch forks after the delete, no branch holds the number"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) == held

    async def test_a_branch_being_deleted_holds_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        """A branch part way through its delete no longer holds anything, before its edges are gone."""
        ticket = await _new_ticket(db=db, pool=pool, title="freed-by-a-deleting-branch")
        held = ticket.get_attribute("ticket_id").value
        older = await create_branch(branch_name="deleting-after-the-delete", db=db)
        await ticket.delete(db=db)
        assert held in await pool.get_used(db=db, branch=default_branch_scope_class)

        await db.execute_query(
            query='MATCH (b:Branch {name: $name}) SET b.status = "DELETING"', params={"name": older.name}
        )

        assert held not in await pool.get_used(db=db, branch=default_branch_scope_class), (
            "a branch being deleted holds nothing, so no branch holds the number"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) == held

    async def test_deleting_the_older_branch_frees_the_number(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        ticket = await _new_ticket(db=db, pool=pool, title="freed-by-a-branch-delete")
        held = ticket.get_attribute("ticket_id").value
        older = await create_branch(branch_name="deleted-after-the-delete", db=db)
        await ticket.delete(db=db)
        assert held in await pool.get_used(db=db, branch=default_branch_scope_class)

        result = await BranchDataDeleter(db=db, batch_size=5).delete(branch=older, user_id=TEST_ACTOR_ID)
        assert result.branch_deleted

        assert held not in await pool.get_used(db=db, branch=default_branch_scope_class), (
            "with the older branch deleted, no branch holds the number"
        )
        assert await pool.get_free(db=db, branch=default_branch_scope_class) == held

    async def test_an_older_branch_that_moved_the_number_itself_holds_only_its_own(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: CoreNumberPool
    ) -> None:
        """The fork point counts a value only while the older branch still reads it, not once it moved on."""
        ticket = await _new_ticket(db=db, pool=pool, title="moved-on-the-older-branch")
        held = ticket.get_attribute("ticket_id").value
        older = await create_branch(branch_name="moves-it-first", db=db)
        on_older = await NodeManager.get_one(db=db, id=ticket.id, branch=older, raise_on_error=True)
        on_older.get_attribute("ticket_id").value = POOL_END
        await on_older.save(db=db)

        await ticket.delete(db=db)

        used = await pool.get_used(db=db, branch=default_branch_scope_class)
        assert POOL_END in used, "the older branch holds the object with the number it moved to"
        assert held not in used, "and no branch holds the number it moved off"
        assert await pool.get_free(db=db, branch=default_branch_scope_class) == held

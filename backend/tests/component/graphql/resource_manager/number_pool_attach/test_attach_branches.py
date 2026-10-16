"""An attach or an allocation from a new pool checks the number every other live branch holds, since a pool tracks an attribute on every branch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from tests.component.core.resource_manager.conftest import delete_branch

from .helpers import (
    UPDATE_TICKET,
    create_ticket,
    new_pool,
    refused_write,
    tracking_pool_id,
    update_ticket,
    used_numbers,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


def _other_branch_message(pool_name: str, held: str, ranges: str) -> str:
    return (
        f"The {pool_name} pool cannot track 'ticket_id', because a pool tracks an attribute on every branch and "
        f"{held} outside its ranges: {ranges}. Change the number on that branch, or delete the branch, before attaching "
        "to or allocating from this pool. at ticket_id.from_pool"
    )


class TestAttachAcrossBranches:
    """The schema is loaded once and tickets accumulate, so every test uses its own pool, numbers and branches."""

    async def test_an_attach_is_refused_while_another_branch_holds_a_number_outside_the_ranges(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="other-branch-outside", start_range=8000, end_range=8009)
        ticket = await create_ticket(db=db, branch=main_branch, title="other-branch-outside", ticket_id={"value": 8005})
        feature = await create_branch(branch_name="holds-8900", db=db)
        await update_ticket(db=db, branch=feature, node_id=ticket["id"], ticket_id={"value": 8900})

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 8005, "from_pool": {"id": pool.id}}},
        )

        assert message == _other_branch_message(
            pool_name="other-branch-outside", held="branch 'holds-8900' holds 8900", ranges="8000-8009"
        )
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == []

    async def test_an_attach_is_refused_while_an_older_branch_holds_a_number_outside_the_ranges_at_its_fork_point(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="older-branch-outside", start_range=8010, end_range=8019)
        ticket = await create_ticket(db=db, branch=main_branch, title="older-branch-outside", ticket_id={"value": 8910})
        older = await create_branch(branch_name="forked-at-8910", db=db)
        await update_ticket(db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 8015})

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 8015, "from_pool": {"id": pool.id}}},
        )

        assert message == _other_branch_message(
            pool_name="older-branch-outside", held=f"branch '{older.name}' holds 8910", ranges="8010-8019"
        )
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == []

    async def test_an_attach_that_moves_the_default_branch_into_the_ranges_is_refused_for_a_newer_branch(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        """The newer branch writes no value of its own, so it holds the number the default branch held when it forked."""
        pool = await new_pool(db=db, name="newer-branch-outside", start_range=8050, end_range=8059)
        ticket = await create_ticket(db=db, branch=main_branch, title="newer-branch-outside", ticket_id={"value": 8950})
        newer = await create_branch(branch_name="inherits-8950", db=db)

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 8051, "from_pool": {"id": pool.id}}},
        )

        assert message == _other_branch_message(
            pool_name="newer-branch-outside", held=f"branch '{newer.name}' holds 8950", ranges="8050-8059"
        )
        reloaded = await NodeManager.get_one(db=db, id=ticket["id"], branch=main_branch)
        assert reloaded is not None
        assert reloaded.get_attribute(name="ticket_id").value == 8950
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == []

    async def test_an_attach_tracks_every_branch_number_when_each_is_inside_the_ranges(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="other-branch-inside", start_range=8020, end_range=8029)
        ticket = await create_ticket(db=db, branch=main_branch, title="other-branch-inside", ticket_id={"value": 8021})
        feature = await create_branch(branch_name="holds-8025", db=db)
        await update_ticket(db=db, branch=feature, node_id=ticket["id"], ticket_id={"value": 8025})

        attached = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 8021, "from_pool": {"id": pool.id}}
        )

        assert attached["ticket_id"]["value"] == 8021
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == pool.id
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [8021, 8025]

    async def test_an_attach_ignores_a_deleted_branch(self, db: InfrahubDatabase, main_branch: Branch) -> None:
        pool = await new_pool(db=db, name="deleted-branch-outside", start_range=8030, end_range=8039)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="deleted-branch-outside", ticket_id={"value": 8031}
        )
        feature = await create_branch(branch_name="held-8930-until-deleted", db=db)
        await update_ticket(db=db, branch=feature, node_id=ticket["id"], ticket_id={"value": 8930})
        await delete_branch(db=db, branch=feature)

        attached = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": 8031, "from_pool": {"id": pool.id}}
        )

        assert attached["ticket_id"]["value"] == 8031
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == pool.id
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [8031]

    async def test_an_attach_on_a_branch_is_refused_while_the_default_branch_holds_a_number_outside_the_ranges(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="default-branch-outside", start_range=8040, end_range=8049)
        ticket = await create_ticket(
            db=db, branch=main_branch, title="default-branch-outside", ticket_id={"value": 8940}
        )
        user_branch = await create_branch(branch_name="attaches-8041", db=db)

        message = await refused_write(
            db=db,
            branch=user_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": 8041, "from_pool": {"id": pool.id}}},
        )

        assert message == _other_branch_message(
            pool_name="default-branch-outside", held=f"branch '{main_branch.name}' holds 8940", ranges="8040-8049"
        )
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) is None
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == []

    async def test_an_allocation_from_another_pool_is_refused_while_another_branch_holds_a_number_outside_its_ranges(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        tracking = await new_pool(db=db, name="allocation-tracking", start_range=8060, end_range=8069)
        target = await new_pool(db=db, name="allocation-target", start_range=8070, end_range=8079)
        ticket = await create_ticket(
            db=db,
            branch=main_branch,
            title="allocation-from-another-pool",
            ticket_id={"value": 8061, "from_pool": {"id": tracking.id}},
        )
        feature = await create_branch(branch_name="holds-8065", db=db)
        await update_ticket(db=db, branch=feature, node_id=ticket["id"], ticket_id={"value": 8065})

        message = await refused_write(
            db=db,
            branch=main_branch,
            source=UPDATE_TICKET,
            variables={"id": ticket["id"], "ticket_id": {"value": None, "from_pool": {"id": target.id}}},
        )

        assert message == _other_branch_message(
            pool_name="allocation-target", held="branch 'holds-8065' holds 8065", ranges="8070-8079"
        )
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == tracking.id
        assert await used_numbers(db=db, branch=main_branch, pool=target) == []

    async def test_an_allocation_that_discards_an_untracked_number_tracks_every_branch_number_inside_the_ranges(
        self, db: InfrahubDatabase, main_branch: Branch
    ) -> None:
        pool = await new_pool(db=db, name="allocation-inside", start_range=8090, end_range=8099)
        ticket = await create_ticket(db=db, branch=main_branch, title="allocation-inside", ticket_id={"value": 8990})
        feature = await create_branch(branch_name="holds-8095", db=db)
        await update_ticket(db=db, branch=feature, node_id=ticket["id"], ticket_id={"value": 8095})

        allocated = await update_ticket(
            db=db, branch=main_branch, node_id=ticket["id"], ticket_id={"value": None, "from_pool": {"id": pool.id}}
        )

        assert allocated["ticket_id"]["value"] == 8090
        assert await tracking_pool_id(db=db, node_id=ticket["id"]) == pool.id
        assert await used_numbers(db=db, branch=main_branch, pool=pool) == [8090, 8095]

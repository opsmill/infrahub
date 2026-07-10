from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.rollback import RollbackQuery, RollbackScope
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def test_restore_metadata_rejected_on_non_default_branch() -> None:
    """A metadata restore is rejected outside the default and global branches.

    The updated_at/by metadata properties exist only on those branches, so requesting a restore
    anywhere else is a caller error.
    """
    with pytest.raises(
        ValueError,
        match=r"^restore_metadata is only allowed when the target branch is the default or global branch$",
    ):
        RollbackQuery(
            at=Timestamp(),
            target_branch=Branch(name="not-default"),
            scope=RollbackScope.SINCE_TIMESTAMP,
            restore_metadata=True,
        )


async def _count_branch_edges_at(db: InfrahubDatabase, branch: Branch, at: Timestamp) -> int:
    result = await db.execute_query(
        query="MATCH ()-[r {from: $at, branch: $branch}]->() RETURN count(r) AS c",
        params={"at": at.to_string(), "branch": branch.name},
    )
    return result[0].get("c")


async def _count_branch_edges_since(db: InfrahubDatabase, branch: Branch, at: Timestamp) -> int:
    result = await db.execute_query(
        query="MATCH ()-[r {branch: $branch}]->() WHERE r.from >= $at RETURN count(r) AS c",
        params={"at": at.to_string(), "branch": branch.name},
    )
    return result[0].get("c")


async def _get_node_vertex_metadata(db: InfrahubDatabase, node_uuid: str) -> dict[str, str | None]:
    result = await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})
        RETURN n.updated_at AS updated_at, n.updated_by AS updated_by,
               n.previous_updated_at AS previous_updated_at, n.previous_updated_by AS previous_updated_by
        """,
        params={"uuid": node_uuid},
    )
    record = result[0]
    return {
        "updated_at": record.get("updated_at"),
        "updated_by": record.get("updated_by"),
        "previous_updated_at": record.get("previous_updated_at"),
        "previous_updated_by": record.get("previous_updated_by"),
    }


async def test_rollback_at_timestamp_only_reverses_that_timestamp(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
) -> None:
    """AT_TIMESTAMP reverses only writes stamped exactly at the given timestamp.

    Clears every edge stamped exactly at the timestamp on the branch and orphan-deletes the
    affected vertices, while leaving writes from earlier AND later timestamps untouched (other
    writers may be active on the branch during the rolled-back operation).
    """
    at_kept = Timestamp()
    kept = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await kept.new(db=db, name="Bob", height=180)
    await kept.save(db=db, at=at_kept)

    at_rolled_back = Timestamp()
    discarded = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await discarded.new(db=db, name="Carol", height=165)
    await discarded.save(db=db, at=at_rolled_back)

    at_later = Timestamp()
    later = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await later.new(db=db, name="Dave", height=175)
    await later.save(db=db, at=at_later)

    edges_before = await _count_branch_edges_at(db=db, branch=default_branch, at=at_rolled_back)
    assert edges_before > 0, "Saving a node should create at least one edge stamped with `at`"

    rollback_query = await RollbackQuery.init(
        db=db,
        target_branch=default_branch,
        at=at_rolled_back,
        scope=RollbackScope.AT_TIMESTAMP,
        restore_metadata=False,
    )
    await rollback_query.execute(db=db)

    loaded_kept = await NodeManager.get_one(db=db, id=kept.id, branch=default_branch)
    assert loaded_kept is not None, "Node created at an earlier timestamp must survive rollback"
    assert loaded_kept.get_attribute("name").value == "Bob"

    loaded_later = await NodeManager.get_one(db=db, id=later.id, branch=default_branch)
    assert loaded_later is not None, "Node created at a later timestamp must survive an exact-timestamp rollback"
    assert loaded_later.get_attribute("name").value == "Dave"

    loaded_discarded = await NodeManager.get_one(db=db, id=discarded.id, branch=default_branch)
    assert loaded_discarded is None, "Node created at the rollback timestamp must be removed"

    edges_after = await _count_branch_edges_at(db=db, branch=default_branch, at=at_rolled_back)
    assert edges_after == 0, "Rollback should delete every edge stamped with `at` on the branch"


@dataclass
class TwoBranchDataset:
    """Pre-window nodes plus the same kinds of in-window changes staged on two branches."""

    branch2: Branch
    window_start: Timestamp
    # default-branch actors
    updated_main: Node
    updated_main_created_at: Timestamp
    deleted_main: Node
    deleted_main_created_at: Timestamp
    created_main: Node
    # user-branch actors
    updated_on_branch: Node
    deleted_on_branch: Node
    created_on_branch: Node


class TestRollbackSinceTimestamp:
    """SINCE_TIMESTAMP reverses a whole window of changes, scoped to its target branch.

    The dataset stages the same change kinds (attribute update, node delete, node creation)
    inside the window on both the default branch and a user branch; each test rolls back one
    branch and verifies the other branch's changes survive untouched.
    """

    @pytest.fixture
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
    ) -> TwoBranchDataset:
        updated_main_created_at = Timestamp()
        updated_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await updated_main.new(db=db, name="Alice", height=170)
        await updated_main.save(db=db, at=updated_main_created_at)

        deleted_main_created_at = Timestamp()
        deleted_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await deleted_main.new(db=db, name="Bob", height=180)
        await deleted_main.save(db=db, at=deleted_main_created_at)

        updated_on_branch = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await updated_on_branch.new(db=db, name="Xena", height=150)
        await updated_on_branch.save(db=db, at=Timestamp())

        deleted_on_branch = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await deleted_on_branch.new(db=db, name="Yara", height=155)
        await deleted_on_branch.save(db=db, at=Timestamp())

        branch2 = await create_branch(db=db, branch_name="branch2")

        window_start = Timestamp()

        # In-window changes on the default branch, each at its own timestamp.
        loaded_updated_main = await NodeManager.get_one(db=db, id=updated_main.id, branch=default_branch)
        loaded_updated_main.get_attribute("name").value = "Alicia"
        await loaded_updated_main.save(db=db, at=Timestamp())

        loaded_deleted_main = await NodeManager.get_one(db=db, id=deleted_main.id, branch=default_branch)
        await loaded_deleted_main.delete(db=db, at=Timestamp())

        created_main = await Node.init(db=db, schema="TestPerson", branch=default_branch)
        await created_main.new(db=db, name="Carol", height=165)
        await created_main.save(db=db, at=Timestamp())

        # In-window changes on the user branch, each at its own timestamp.
        loaded_updated_on_branch = await NodeManager.get_one(db=db, id=updated_on_branch.id, branch=branch2)
        loaded_updated_on_branch.get_attribute("name").value = "Xena-branch"
        await loaded_updated_on_branch.save(db=db, at=Timestamp())

        loaded_deleted_on_branch = await NodeManager.get_one(db=db, id=deleted_on_branch.id, branch=branch2)
        await loaded_deleted_on_branch.delete(db=db, at=Timestamp())

        created_on_branch = await Node.init(db=db, schema="TestPerson", branch=branch2)
        await created_on_branch.new(db=db, name="Zoe", height=165)
        await created_on_branch.save(db=db, at=Timestamp())

        # manually update previous_updated_at/by metadata as would happen during a merge operation
        await db.execute_query(
            query="""
            UNWIND $stamps AS stamp
            MATCH (n:Node {uuid: stamp.uuid})
            SET n.previous_updated_at = stamp.previous_at, n.previous_updated_by = $previous_by
            """,
            params={
                "stamps": [
                    {"uuid": updated_main.id, "previous_at": updated_main_created_at.to_string()},
                    {"uuid": deleted_main.id, "previous_at": deleted_main_created_at.to_string()},
                ],
                "previous_by": "original-user",
            },
        )

        return TwoBranchDataset(
            branch2=branch2,
            window_start=window_start,
            updated_main=updated_main,
            updated_main_created_at=updated_main_created_at,
            deleted_main=deleted_main,
            deleted_main_created_at=deleted_main_created_at,
            created_main=created_main,
            updated_on_branch=updated_on_branch,
            deleted_on_branch=deleted_on_branch,
            created_on_branch=created_on_branch,
        )

    async def _assert_default_branch_rolled_back(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: TwoBranchDataset
    ) -> None:
        restored_person = await NodeManager.get_one(db=db, id=dataset.updated_main.id, branch=default_branch)
        assert restored_person is not None, "Node created before the window must survive rollback"
        assert restored_person.get_attribute("name").value == "Alice", "In-window attribute update must be reverted"

        restored_deleted_person = await NodeManager.get_one(db=db, id=dataset.deleted_main.id, branch=default_branch)
        assert restored_deleted_person is not None, "Node deleted inside the window must be restored"
        assert restored_deleted_person.get_attribute("name").value == "Bob"

        loaded_created_in_window = await NodeManager.get_one(db=db, id=dataset.created_main.id, branch=default_branch)
        assert loaded_created_in_window is None, "Node created inside the window must be removed"

        edges_after = await _count_branch_edges_since(db=db, branch=default_branch, at=dataset.window_start)
        assert edges_after == 0, "Rollback should delete every branch edge created at or after the window start"

        metadata = await _get_node_vertex_metadata(db=db, node_uuid=dataset.updated_main.id)
        assert metadata["updated_at"] == dataset.updated_main_created_at.to_string(), (
            "updated_at must be restored from its snapshot"
        )
        assert metadata["updated_by"] == "original-user", "updated_by must be restored from its snapshot"
        assert metadata["previous_updated_at"] is None, "The snapshot must be cleared after the restore"
        assert metadata["previous_updated_by"] is None, "The snapshot must be cleared after the restore"

        deleted_metadata = await _get_node_vertex_metadata(db=db, node_uuid=dataset.deleted_main.id)
        assert deleted_metadata["updated_at"] == dataset.deleted_main_created_at.to_string(), (
            "The restored node's updated_at must come from its snapshot, not the delete time"
        )
        assert deleted_metadata["updated_by"] == "original-user"
        assert deleted_metadata["previous_updated_at"] is None, "The snapshot must be cleared after the restore"
        assert deleted_metadata["previous_updated_by"] is None, "The snapshot must be cleared after the restore"

    async def _assert_user_branch_changes_intact(self, db: InfrahubDatabase, dataset: TwoBranchDataset) -> None:
        updated = await NodeManager.get_one(db=db, id=dataset.updated_on_branch.id, branch=dataset.branch2)
        assert updated is not None
        assert updated.get_attribute("name").value == "Xena-branch", (
            "The user branch's attribute update must survive a default-branch rollback"
        )

        deleted = await NodeManager.get_one(db=db, id=dataset.deleted_on_branch.id, branch=dataset.branch2)
        assert deleted is None, "The user branch's node delete must survive a default-branch rollback"

        created = await NodeManager.get_one(db=db, id=dataset.created_on_branch.id, branch=dataset.branch2)
        assert created is not None, "The node created on the user branch must survive a default-branch rollback"

    async def test_default_branch_rollback_restores_metadata_and_leaves_user_branch_untouched(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        dataset: TwoBranchDataset,
    ) -> None:
        rollback_query = await RollbackQuery.init(
            db=db,
            target_branch=default_branch,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
            restore_metadata=True,
        )
        await rollback_query.execute(db=db)

        await self._assert_default_branch_rolled_back(db=db, default_branch=default_branch, dataset=dataset)
        await self._assert_user_branch_changes_intact(db=db, dataset=dataset)

        # Idempotent: a second run finds nothing in the window and leaves the restored state alone.
        rerun_query = await RollbackQuery.init(
            db=db,
            target_branch=default_branch,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
            restore_metadata=True,
        )
        await rerun_query.execute(db=db)

        await self._assert_default_branch_rolled_back(db=db, default_branch=default_branch, dataset=dataset)
        await self._assert_user_branch_changes_intact(db=db, dataset=dataset)

    async def test_user_branch_rollback_leaves_default_branch_untouched(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        dataset: TwoBranchDataset,
    ) -> None:
        rollback_query = await RollbackQuery.init(
            db=db,
            target_branch=dataset.branch2,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
            restore_metadata=False,
        )
        await rollback_query.execute(db=db)

        # The user branch's window is reverted: its view falls back to the default-branch state.
        updated = await NodeManager.get_one(db=db, id=dataset.updated_on_branch.id, branch=dataset.branch2)
        assert updated is not None
        assert updated.get_attribute("name").value == "Xena", "The branch attribute update must be reverted"

        deleted = await NodeManager.get_one(db=db, id=dataset.deleted_on_branch.id, branch=dataset.branch2)
        assert deleted is not None, "The node deleted on the branch must be restored"
        assert deleted.get_attribute("name").value == "Yara"

        created = await NodeManager.get_one(db=db, id=dataset.created_on_branch.id, branch=dataset.branch2)
        assert created is None, "The node created on the branch must be removed"

        edges_after = await _count_branch_edges_since(db=db, branch=dataset.branch2, at=dataset.window_start)
        assert edges_after == 0, "Rollback should delete every user-branch edge created in the window"

        # The default branch's in-window changes are untouched.
        alice = await NodeManager.get_one(db=db, id=dataset.updated_main.id, branch=default_branch)
        assert alice.get_attribute("name").value == "Alicia", (
            "The default branch's attribute update must survive a user-branch rollback"
        )

        bob = await NodeManager.get_one(db=db, id=dataset.deleted_main.id, branch=default_branch)
        assert bob is None, "The default branch's node delete must survive a user-branch rollback"

        carol = await NodeManager.get_one(db=db, id=dataset.created_main.id, branch=default_branch)
        assert carol is not None, "The node created on the default branch must survive a user-branch rollback"

        default_edges = await _count_branch_edges_since(db=db, branch=default_branch, at=dataset.window_start)
        assert default_edges > 0, "The default branch's in-window edges must survive a user-branch rollback"

        # No metadata was restored: the default-branch snapshots are still in place.
        metadata = await _get_node_vertex_metadata(db=db, node_uuid=dataset.updated_main.id)
        assert metadata["previous_updated_at"] == dataset.updated_main_created_at.to_string(), (
            "A user-branch rollback must not consume default-branch metadata snapshots"
        )
        assert metadata["previous_updated_by"] == "original-user"

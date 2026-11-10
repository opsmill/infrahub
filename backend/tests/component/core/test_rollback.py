from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.timestamp import Timestamp
from tests.helpers.agnostic_edges import (
    VertexMetadata,
    attribute_global_edges,
    attribute_metadata,
    edge_summary,
    open_edges,
)
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA, WIDGET_KIND

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def assert_no_changes_at_or_after(db: InfrahubDatabase, branch: Branch, at_or_after: Timestamp) -> None:
    """Assert that no edges exist on the branch at or after the given timestamp."""
    query = """
    MATCH ()-[r {branch: $branch}]->()
    WHERE r.from >= $at
    OR r.to >= $at
    RETURN collect(elementId(r)) AS edge_ids
    """
    result = await db.execute_query(
        query=query,
        params={"at": at_or_after.to_string(), "branch": branch.name},
    )
    assert result
    illegal_edge_ids = result[0].get("edge_ids")
    assert illegal_edge_ids == [], f"Edges updated after {at_or_after} on branch {branch.name}: {illegal_edge_ids}"


async def assert_no_orphan_vertices(db: InfrahubDatabase) -> None:
    """Assert that no vertex is left without a single connection.

    The rollback's edge deletions must take the vertices they orphan down with them.
    """
    result = await db.execute_query(
        query="MATCH (n) WHERE NOT exists((n)--()) RETURN count(n) AS orphan_count",
    )
    assert result[0].get("orphan_count") == 0


async def _count_vertices_with_uuid(db: InfrahubDatabase, uuid: str) -> int:
    result = await db.execute_query(
        query="MATCH (n {uuid: $uuid}) RETURN count(n) AS c",
        params={"uuid": uuid},
    )
    return result[0].get("c")


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

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=at_rolled_back,
        scope=RollbackScope.AT_TIMESTAMP,
    )

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

    assert await _count_vertices_with_uuid(db=db, uuid=discarded.id) == 0, (
        "The removed node's own vertices must not survive as orphans"
    )
    await assert_no_orphan_vertices(db=db)


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

    The default-branch update and delete land exactly at the window start, the way a merge stamps
    every write at its own timestamp — the metadata restore matches only that stamp. The creation
    and the user-branch changes land later inside the window, proving the range still reverses
    edges past the exact stamp.
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

        # In-window changes on the default branch: the update and delete at the operation's own
        # timestamp (the stamp the metadata restore matches), the creation later in the window.
        loaded_updated_main = await NodeManager.get_one(db=db, id=updated_main.id, branch=default_branch)
        loaded_updated_main.get_attribute("name").value = "Alicia"
        await loaded_updated_main.save(db=db, at=window_start)

        loaded_deleted_main = await NodeManager.get_one(db=db, id=deleted_main.id, branch=default_branch)
        await loaded_deleted_main.delete(db=db, at=window_start)

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

        assert await _count_vertices_with_uuid(db=db, uuid=dataset.created_main.id) == 0, (
            "The removed node's own vertices must not survive as orphans"
        )
        await assert_no_orphan_vertices(db=db)

        await assert_no_changes_at_or_after(db=db, branch=default_branch, at_or_after=dataset.window_start)

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

    async def _assert_user_branch_rolled_back(self, db: InfrahubDatabase, dataset: TwoBranchDataset) -> None:
        # The user branch's window is reverted: its view falls back to the default-branch state.
        updated = await NodeManager.get_one(db=db, id=dataset.updated_on_branch.id, branch=dataset.branch2)
        assert updated is not None
        assert updated.get_attribute("name").value == "Xena", "The branch attribute update must be reverted"

        deleted = await NodeManager.get_one(db=db, id=dataset.deleted_on_branch.id, branch=dataset.branch2)
        assert deleted is not None, "The node deleted on the branch must be restored"
        assert deleted.get_attribute("name").value == "Yara"

        created = await NodeManager.get_one(db=db, id=dataset.created_on_branch.id, branch=dataset.branch2)
        assert created is None, "The node created on the branch must be removed"

        assert await _count_vertices_with_uuid(db=db, uuid=dataset.created_on_branch.id) == 0, (
            "The removed node's own vertices must not survive as orphans"
        )
        await assert_no_orphan_vertices(db=db)

        await assert_no_changes_at_or_after(db=db, branch=dataset.branch2, at_or_after=dataset.window_start)

    async def _assert_default_branch_changes_intact(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: TwoBranchDataset
    ) -> None:
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

        # The restore matches only the rolled-back operation's exact timestamp, so the
        # default-branch snapshots are still in place.
        metadata = await _get_node_vertex_metadata(db=db, node_uuid=dataset.updated_main.id)
        assert metadata["previous_updated_at"] == dataset.updated_main_created_at.to_string(), (
            "A user-branch rollback must not consume default-branch metadata snapshots"
        )
        assert metadata["previous_updated_by"] == "original-user"

    async def test_default_branch_rollback_restores_metadata_and_leaves_user_branch_untouched(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        dataset: TwoBranchDataset,
    ) -> None:
        await GraphRollbacker(db=db).rollback(
            target_branch=default_branch,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
        )

        await self._assert_default_branch_rolled_back(db=db, default_branch=default_branch, dataset=dataset)
        await self._assert_user_branch_changes_intact(db=db, dataset=dataset)

        # Idempotent: a second run finds nothing in the window and leaves the restored state alone.
        await GraphRollbacker(db=db).rollback(
            target_branch=default_branch,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
        )

        await self._assert_default_branch_rolled_back(db=db, default_branch=default_branch, dataset=dataset)
        await self._assert_user_branch_changes_intact(db=db, dataset=dataset)

    async def test_user_branch_rollback_leaves_default_branch_untouched(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        dataset: TwoBranchDataset,
    ) -> None:
        await GraphRollbacker(db=db).rollback(
            target_branch=dataset.branch2,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
        )

        await self._assert_user_branch_rolled_back(db=db, dataset=dataset)
        await self._assert_default_branch_changes_intact(db=db, default_branch=default_branch, dataset=dataset)

        # Idempotent: a second run finds nothing in the window and leaves the restored state alone.
        await GraphRollbacker(db=db).rollback(
            target_branch=dataset.branch2,
            at=dataset.window_start,
            scope=RollbackScope.SINCE_TIMESTAMP,
        )

        await self._assert_user_branch_rolled_back(db=db, dataset=dataset)
        await self._assert_default_branch_changes_intact(db=db, default_branch=default_branch, dataset=dataset)


AGNOSTIC_ATTRIBUTE_NAME = "serial"


@pytest.fixture
async def agnostic_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


async def test_rollback_undoes_a_branch_agnostic_write_in_both_directions(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """Update branch-agnostic value to close an edge and create one. Verify rollback undoes it."""
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="changes-its-serial", serial=500)
    await widget.save(db=db)

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)

    changed_at = Timestamp()
    reloaded = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
    reloaded.get_attribute(name=AGNOSTIC_ATTRIBUTE_NAME).value = 600
    await reloaded.save(db=db, at=changed_at)

    changed = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert len(changed) > len(before), "precondition: the write added a global edge for the new value"

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=changed_at,
        scope=RollbackScope.AT_TIMESTAMP,
    )

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert edge_summary(after) == edge_summary(before), (
        "the edge the write created is gone and the one it closed is open again"
    )


async def _close_global_edges_by_hand(db: InfrahubDatabase, node_id: str, attribute_name: str, at: Timestamp) -> None:
    """Close a branch-agnostic attribute's open global edges, as a schema removal migration would."""
    await db.execute_query(
        query="""
        MATCH (n:Node { uuid: $uuid })-[:HAS_ATTRIBUTE]-(a:Attribute { name: $attr })
        MATCH (a)-[e]-()
        WHERE e.branch = $global_branch AND e.status = "active" AND e.to IS NULL AND e.from <= $at
        SET e.to = $at
        """,
        params={"uuid": node_id, "attr": attribute_name, "global_branch": GLOBAL_BRANCH_NAME, "at": at.to_string()},
    )


async def test_range_scoped_rollback_reopens_global_edges_closed_at_its_own_timestamp(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="closed-during-a-merge", serial=700)
    await widget.save(db=db)

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert open_edges(before) != []

    merge_at = Timestamp()
    await _close_global_edges_by_hand(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME, at=merge_at)
    assert (
        open_edges(await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)) == []
    )

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=merge_at,
        scope=RollbackScope.SINCE_TIMESTAMP,
    )

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert edge_summary(after) == edge_summary(before), "the closures the rolled-back operation made are reversed"


async def test_range_scoped_rollback_leaves_global_edges_closed_at_another_timestamp(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="closed-by-someone-else", serial=701)
    await widget.save(db=db)

    merge_at = Timestamp()
    someone_else_at = merge_at.add(microseconds=1)

    await _close_global_edges_by_hand(
        db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME, at=someone_else_at
    )
    closed = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert open_edges(closed) == [], "precondition: the other writer's closure left no open global edge"

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=merge_at,
        scope=RollbackScope.SINCE_TIMESTAMP,
    )

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert edge_summary(after) == edge_summary(closed), "another writer's closure is left alone"


async def _bump_node_metadata_by_hand(db: InfrahubDatabase, node_id: str, at: Timestamp, by: str) -> None:
    """Bump a node vertex's audit stamps as a write would, snapshotting the values it overwrites."""
    await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})
        SET n.previous_updated_at = n.updated_at, n.previous_updated_by = n.updated_by
        SET n.updated_at = $at, n.updated_by = $by
        """,
        params={"uuid": node_id, "at": at.to_string(), "by": by},
    )


async def _bump_attribute_metadata_by_hand(
    db: InfrahubDatabase, node_id: str, attribute_name: str, at: Timestamp, by: str
) -> None:
    """Bump an attribute vertex's audit stamps as a global-edge closure would."""
    await db.execute_query(
        query="""
        MATCH (:Node {uuid: $uuid})-[:HAS_ATTRIBUTE]->(v:Attribute {name: $attr})
        SET v.previous_updated_at = v.updated_at, v.previous_updated_by = v.updated_by
        SET v.updated_at = $at, v.updated_by = $by
        """,
        params={"uuid": node_id, "attr": attribute_name, "at": at.to_string(), "by": by},
    )


async def test_range_scoped_rollback_leaves_metadata_bumped_by_a_later_unrelated_write(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """A vertex bumped inside the range window, but after the operation, keeps its stamps.

    Test the case where an unrelated update to a branch-agnostic attribute on a different branch
    is executed after the rollback timestamp but before the rollback runs. An example:
    1. Merge Branch A starts
    2. widget.something updated on Branch B (where something is a branch-agnostic attribute)
    3. Merge of Branch A fails and rollback begins

    In this case the rollback should NOT undo updated_at/by metadata for the change on Branch B
    b/c that change will remain in place after the rollback completes.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="bumped-by-another-writer", serial=702)
    await widget.save(db=db)

    merge_at = Timestamp()
    reloaded = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
    reloaded.get_attribute(name="name").value = "renamed-in-the-window"
    await reloaded.save(db=db, at=merge_at)

    later_at = Timestamp()
    await _bump_node_metadata_by_hand(db=db, node_id=widget.id, at=later_at, by="another-writer")
    bumped = await _get_node_vertex_metadata(db=db, node_uuid=widget.id)
    assert bumped["updated_at"] == later_at.to_string()

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=merge_at,
        scope=RollbackScope.SINCE_TIMESTAMP,
    )

    after = await _get_node_vertex_metadata(db=db, node_uuid=widget.id)
    assert after == bumped, "the later writer's stamps and snapshot survive the rollback byte-identical"


async def test_rollback_restores_a_vertex_reached_through_both_branches_once(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """One write touching both field kinds is restored once, back to the pre-operation stamps.

    Updating a branch-aware and a branch-agnostic attribute in one save reaches the owning node
    vertex through a target-branch edge and a global-branch edge in the same rollback. The restore
    must fire exactly once for it: `updated_at` back to the pre-operation value -- never NULL --
    and the snapshot cleared.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="two-axis", serial=800)
    await widget.save(db=db)

    before_meta = await _get_node_vertex_metadata(db=db, node_uuid=widget.id)
    assert before_meta["updated_at"] is not None, "precondition: creating the object stamped the node"
    before_edges = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)

    merge_at = Timestamp()
    reloaded = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
    reloaded.get_attribute(name="name").value = "two-axis-renamed"
    reloaded.get_attribute(name=AGNOSTIC_ATTRIBUTE_NAME).value = 801
    await reloaded.save(db=db, at=merge_at)

    # The write bumps the stamps; snapshot the overwritten values by hand, as a merge's bump does.
    await db.execute_query(
        query="""
        MATCH (n:Node {uuid: $uuid})
        SET n.previous_updated_at = $previous_at, n.previous_updated_by = $previous_by
        """,
        params={
            "uuid": widget.id,
            "previous_at": before_meta["updated_at"],
            "previous_by": before_meta["updated_by"],
        },
    )
    bumped = await _get_node_vertex_metadata(db=db, node_uuid=widget.id)
    assert bumped["updated_at"] == merge_at.to_string(), "precondition: the operation stamped the node"

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=merge_at,
        scope=RollbackScope.SINCE_TIMESTAMP,
    )

    after_meta = await _get_node_vertex_metadata(db=db, node_uuid=widget.id)
    assert after_meta == {
        "updated_at": before_meta["updated_at"],
        "updated_by": before_meta["updated_by"],
        "previous_updated_at": None,
        "previous_updated_by": None,
    }, "restored once, to the pre-operation stamps, with the snapshot cleared"

    after_edges = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert edge_summary(after_edges) == edge_summary(before_edges), "the agnostic write is reversed alongside"


async def test_user_branch_rollback_restores_metadata_stamped_by_its_global_writes(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The exact-timestamp global pass restores stamps whatever the target branch is.

    A schema removal on a user branch closes global edges and stamps the vertices it touched;
    rolling the removal back with the user branch as the target must restore those stamps -- the
    global branch is covered by every rollback, and the restore no longer depends on the target
    being the default branch.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="closed-from-a-user-branch", serial=900)
    await widget.save(db=db)
    user_branch = await create_branch(db=db, branch_name="closes-a-global-edge")

    before_edges = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert open_edges(before_edges) != []
    before_meta = await attribute_metadata(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)

    removed_at = Timestamp()
    await _close_global_edges_by_hand(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME, at=removed_at)
    await _bump_attribute_metadata_by_hand(
        db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME, at=removed_at, by="migration-user"
    )

    await GraphRollbacker(db=db).rollback(
        target_branch=user_branch,
        at=removed_at,
        scope=RollbackScope.AT_TIMESTAMP,
    )

    after_edges = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert edge_summary(after_edges) == edge_summary(before_edges), "the closures are reopened"

    after_meta = await attribute_metadata(db=db, node_id=widget.id, attribute_name=AGNOSTIC_ATTRIBUTE_NAME)
    assert after_meta == VertexMetadata(
        updated_at=before_meta.updated_at,
        updated_by=before_meta.updated_by,
        previous_updated_at=None,
        previous_updated_by=None,
    ), "the stamps the closure wrote are restored"

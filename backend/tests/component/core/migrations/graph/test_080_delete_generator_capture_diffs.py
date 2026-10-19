from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import EnrichedDiffRootMetadata
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m080_delete_generator_capture_diffs import Migration080
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry

DIFF_VERTEX_LABELS = [
    "DiffRoot",
    "DiffNode",
    "DiffAttribute",
    "DiffRelationship",
    "DiffRelationshipElement",
    "DiffProperty",
    "DiffConflict",
]


class FailingDiffRepository(DiffRepository):
    """Deletes for real, except for the diff holding one root, where it raises instead."""

    def __init__(self, db: InfrahubDatabase, failing_root_uuid: str) -> None:
        super().__init__(db=db, deserializer=EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdder()))
        self.failing_root_uuid = failing_root_uuid
        self.attempted: list[list[str]] = []

    async def delete_diff_roots(self, diff_root_uuids: list[str], include_frozen: bool = False) -> None:
        self.attempted.append(diff_root_uuids)
        if self.failing_root_uuid in diff_root_uuids:
            raise ValueError("FAILED")
        await super().delete_diff_roots(diff_root_uuids=diff_root_uuids, include_frozen=include_frozen)


class Migration080WithFailingRepository(Migration080):
    model_config = {"arbitrary_types_allowed": True}

    failing_root_uuid: str = ""
    diff_repository: FailingDiffRepository | None = None

    def build_diff_repository(self, db: InfrahubDatabase) -> DiffRepository:
        self.diff_repository = FailingDiffRepository(db=db, failing_root_uuid=self.failing_root_uuid)
        return self.diff_repository


def root_uuids(diff: EnrichedDiffRootMetadata) -> list[str]:
    return sorted({diff.uuid, diff.partner_uuid or diff.uuid})


async def diff_vertex_ids(db: InfrahubDatabase, of_root_uuids: list[str] | None = None) -> set[str]:
    """Return every diff vertex, or only those of the diffs with these roots."""
    if of_root_uuids is None:
        query = "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) RETURN elementId(n) AS id"
    else:
        query = """
MATCH (root:DiffRoot) WHERE root.uuid IN $root_uuids
RETURN elementId(root) AS id
UNION
MATCH (root:DiffRoot)-[*]->(n)
WHERE root.uuid IN $root_uuids AND any(label IN labels(n) WHERE label IN $labels)
RETURN elementId(n) AS id
        """
    results = await db.execute_query(query=query, params={"labels": DIFF_VERTEX_LABELS, "root_uuids": of_root_uuids})
    return {result["id"] for result in results}


async def stored_root_uuids(db: InfrahubDatabase) -> set[str]:
    results = await db.execute_query(query="MATCH (root:DiffRoot) RETURN root.uuid AS uuid")
    return {result["uuid"] for result in results}


class TestMigration080:
    @pytest.fixture(autouse=True)
    async def _setup_core_schema(self, register_core_models_schema: SchemaBranch) -> None:
        return

    @pytest.fixture
    async def diff_coordinator(self, db: InfrahubDatabase, default_branch: Branch) -> DiffCoordinator:
        return await get_component_registry().get_component(DiffCoordinator, db=db, branch=default_branch)

    async def _store_named_diff(
        self, diff_coordinator: DiffCoordinator, default_branch: Branch, from_time: Timestamp, name: str
    ) -> EnrichedDiffRootMetadata:
        return await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=default_branch,
            diff_branch=default_branch,
            from_time=from_time,
            to_time=Timestamp(),
            name=name,
        )

    async def _store_capture_diff(
        self, diff_coordinator: DiffCoordinator, default_branch: Branch, from_time: Timestamp
    ) -> EnrichedDiffRootMetadata:
        return await self._store_named_diff(
            diff_coordinator=diff_coordinator,
            default_branch=default_branch,
            from_time=from_time,
            name=f"selective-regen-capture--{uuid4()}",
        )

    async def test_deletes_only_the_capture_diffs(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        diff_coordinator: DiffCoordinator,
    ) -> None:
        from_time = Timestamp()
        car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        car.nbr_seats.value = 7
        await car.save(db=db)

        capture_diffs = [
            await self._store_capture_diff(
                diff_coordinator=diff_coordinator, default_branch=default_branch, from_time=from_time
            )
            for _ in range(2)
        ]
        # A diff of the default branch against itself is stored as a single root, with no partner.
        assert [root_uuids(diff) for diff in capture_diffs] == [[diff.uuid] for diff in capture_diffs]
        named_diff = await self._store_named_diff(
            diff_coordinator=diff_coordinator, default_branch=default_branch, from_time=from_time, name=str(uuid4())
        )
        frozen_capture_diff = await self._store_capture_diff(
            diff_coordinator=diff_coordinator, default_branch=default_branch, from_time=from_time
        )
        await db.execute_query(
            query="MATCH (root:DiffRoot {uuid: $uuid}) SET root.is_frozen = TRUE",
            params={"uuid": frozen_capture_diff.uuid},
        )
        # Deleting a root also deletes what its partner edge points to, so these two capture diffs are kept as well.
        capture_diffs_with_kept_partner = [
            await self._store_capture_diff(
                diff_coordinator=diff_coordinator, default_branch=default_branch, from_time=from_time
            )
            for _ in range(2)
        ]
        for capture_diff, kept_partner in zip(
            capture_diffs_with_kept_partner, [named_diff, frozen_capture_diff], strict=True
        ):
            await db.execute_query(
                query="""
MATCH (root:DiffRoot {uuid: $root_uuid}), (partner:DiffRoot {uuid: $partner_uuid})
CREATE (root)-[:DIFF_HAS_PARTNER]->(partner)
                """,
                params={"root_uuid": capture_diff.uuid, "partner_uuid": kept_partner.uuid},
            )
        branch = await create_branch(db=db, branch_name="branch1")
        car_on_branch = await NodeManager.get_one(db=db, branch=branch, id=car_accord_main.id)
        car_on_branch.nbr_seats.value = 3
        await car_on_branch.save(db=db)
        branch_diff = await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)

        kept_root_uuids = [
            *root_uuids(named_diff),
            *root_uuids(frozen_capture_diff),
            *[uuid for diff in capture_diffs_with_kept_partner for uuid in root_uuids(diff)],
            *root_uuids(branch_diff),
        ]
        capture_root_uuids = [uuid for diff in capture_diffs for uuid in root_uuids(diff)]
        all_vertices_before = await diff_vertex_ids(db=db)
        kept_vertices_before = await diff_vertex_ids(db=db, of_root_uuids=kept_root_uuids)
        assert await stored_root_uuids(db=db) == {*kept_root_uuids, *capture_root_uuids}
        # The capture diffs hold more than their roots, so the subtrees below them are deleted too.
        assert len(all_vertices_before - kept_vertices_before) > len(capture_root_uuids)

        migration = Migration080()
        for _ in range(2):
            execution_result = await migration.execute(migration_input=MigrationInput(db=db))
            assert execution_result.errors == []
            validation_result = await migration.validate_migration(db=db)
            assert validation_result.errors == []

            assert await stored_root_uuids(db=db) == set(kept_root_uuids)
            assert await diff_vertex_ids(db=db) == kept_vertices_before

    async def test_one_failing_diff_does_not_block_the_others(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        diff_coordinator: DiffCoordinator,
    ) -> None:
        from_time = Timestamp()
        car = await NodeManager.get_one(db=db, id=car_accord_main.id)
        car.nbr_seats.value = 7
        await car.save(db=db)
        capture_diffs = sorted(
            [
                root_uuids(
                    await self._store_capture_diff(
                        diff_coordinator=diff_coordinator, default_branch=default_branch, from_time=from_time
                    )
                )
                for _ in range(3)
            ]
        )
        failing_diff = capture_diffs[1]

        migration = Migration080WithFailingRepository(failing_root_uuid=failing_diff[0])
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))

        assert execution_result.errors == [f"diff with roots {failing_diff}: FAILED"]
        assert migration.diff_repository is not None
        assert migration.diff_repository.attempted == capture_diffs
        assert await stored_root_uuids(db=db) == set(failing_diff)
        validation_result = await migration.validate_migration(db=db)
        assert validation_result.errors == [f"1 generator capture diff(s) remain: {[failing_diff]}"]

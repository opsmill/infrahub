import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

import pytest

from infrahub.cli.db import load_export
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.node import Node
from infrahub.core.ownership.constants import NO_OWNER_VERTEX_UUID
from infrahub.core.ownership.models import NODE_HOLDER, NODE_SOURCES_HOLDER, HolderKey, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.patch.edge_adder import PatchPlanEdgeAdder
from infrahub.patch.edge_deleter import PatchPlanEdgeDeleter
from infrahub.patch.edge_updater import PatchPlanEdgeUpdater
from infrahub.patch.plan_reader import PatchPlanReader
from infrahub.patch.plan_writer import PatchPlanWriter
from infrahub.patch.queries.delete_duplicated_edges import DeleteDuplicatedEdgesPatchQuery
from infrahub.patch.runner import (
    PatchPlanEdgeDbIdTranslator,
    PatchRunner,
)
from infrahub.patch.vertex_adder import PatchPlanVertexAdder
from infrahub.patch.vertex_deleter import PatchPlanVertexDeleter
from infrahub.patch.vertex_updater import PatchPlanVertexUpdater


class TestKindMigrationDeduplicationPatches:
    @pytest.fixture(scope="class")
    def temporary_directory_path(self) -> Generator[Path, None, None]:
        temporary_directory = tempfile.TemporaryDirectory()
        yield Path(temporary_directory.name)
        temporary_directory.cleanup()

    @pytest.fixture(scope="class", autouse=True)
    async def load_bad_data(self, db: InfrahubDatabase) -> None:
        await delete_all_nodes(db=db)
        export_dir = Path(__file__).parent / ("data_export")
        await load_export(db=db, export_dir=export_dir)

    def get_patch_runner(self, db: InfrahubDatabase) -> PatchRunner:
        return PatchRunner(
            plan_writer=PatchPlanWriter(),
            plan_reader=PatchPlanReader(),
            edge_db_id_translator=PatchPlanEdgeDbIdTranslator(),
            vertex_adder=PatchPlanVertexAdder(db=db, batch_size_limit=1),
            vertex_deleter=PatchPlanVertexDeleter(db=db, batch_size_limit=1),
            vertex_updater=PatchPlanVertexUpdater(db=db, batch_size_limit=1),
            edge_adder=PatchPlanEdgeAdder(db=db, batch_size_limit=1),
            edge_deleter=PatchPlanEdgeDeleter(db=db, batch_size_limit=1),
            edge_updater=PatchPlanEdgeUpdater(db=db, batch_size_limit=1),
        )

    async def validate_edge_deduplication_patch(self, db: InfrahubDatabase) -> list[str]:
        query = """
MATCH (a)-[e]->(b)
WITH DISTINCT a, b, type(e) AS edge_type
CALL (a, b, edge_type) {
    MATCH (a)-[e]->(b)
    WHERE type(e) = edge_type
    WITH %(id_func)s(a) as db_id_a, %(id_func)s(b) as db_id_b, e.branch AS branch, e.status AS status, count(*) AS num_dups
    WHERE num_dups > 1
    RETURN db_id_a, db_id_b, branch, status, num_dups
}
RETURN db_id_a, db_id_b, edge_type, branch, status, num_dups
        """ % {"id_func": db.get_id_function_name()}
        results = await db.execute_query(query=query)
        errors = []
        for result in results:
            db_id_a = result.get("db_id_a")
            db_id_b = result.get("db_id_b")
            edge_type = result.get("edge_type")
            branch = result.get("branch")
            status = result.get("status")
            num_dups = result.get("num_dups")
            errors.append(
                f"{num_dups} duplicate edges exist for {db_id_a=}, {db_id_b=}, {edge_type=}, {branch=}, {status=}"
            )
        return errors

    async def test_edge_deduplication_patch(self, db: InfrahubDatabase, temporary_directory_path: Path) -> None:
        before_errors = await self.validate_edge_deduplication_patch(db=db)
        assert before_errors

        patch_runner = self.get_patch_runner(db=db)
        patch_plan_dir = await patch_runner.prepare_plan(
            patch_query=DeleteDuplicatedEdgesPatchQuery(db=db), directory=temporary_directory_path
        )
        await patch_runner.apply(patch_plan_directory=patch_plan_dir)

        after_errors = await self.validate_edge_deduplication_patch(db=db)
        assert not after_errors


@dataclass
class OwnerReAddTestCase:
    name: str
    holder: HolderKey
    edge_type: DatabaseEdgeType
    states: list[tuple[str, ...]]
    """Group names for each write, in order. An empty tuple is the "no owner" state, or no source."""

    peer_name: str
    """The group that gets two edges, or the `NoOwner` vertex."""


OWNER_RE_ADD_TEST_CASES: list[OwnerReAddTestCase] = [
    OwnerReAddTestCase(
        name="node_owner",
        holder=NODE_HOLDER,
        edge_type=DatabaseEdgeType.HAS_OWNER,
        states=[("dc-emea",), ("network-emea",), ("dc-emea",)],
        peer_name="dc-emea",
    ),
    OwnerReAddTestCase(
        name="node_no_owner",
        holder=NODE_HOLDER,
        edge_type=DatabaseEdgeType.HAS_OWNER,
        states=[(), ("dc-emea",), ()],
        peer_name=NO_OWNER_VERTEX_UUID,
    ),
    OwnerReAddTestCase(
        name="node_source",
        holder=NODE_SOURCES_HOLDER,
        edge_type=DatabaseEdgeType.HAS_SOURCE,
        states=[("dc-emea",), (), ("dc-emea",)],
        peer_name="dc-emea",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_RE_ADD_TEST_CASES])
async def test_edge_deduplication_plan_keeps_owner_added_again(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: SchemaBranch,
    test_case: OwnerReAddTestCase,
) -> None:
    peer_ids = {NO_OWNER_VERTEX_UUID: NO_OWNER_VERTEX_UUID}
    for group_name in ("dc-emea", "network-emea"):
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name=group_name)
        await group.save(db=db)
        peer_ids[group_name] = group.id
    person = await Node.init(db=db, schema="TestPerson")
    await person.new(db=db, name="John")
    await person.save(db=db)

    repository = OwnershipRepository(db=db, branch=default_branch, at=None)
    for group_names in test_case.states:
        await repository.write(
            node_id=person.id,
            holder=test_case.holder,
            state=StoredOwnerState(owner_ids=tuple(peer_ids[group_name] for group_name in group_names)),
            write_branch=default_branch,
            at=Timestamp(),
            user_id="test-user-id",
        )

    records = await db.execute_query(
        query=f"""
MATCH (:Node {{uuid: $node_id}})-[e:{test_case.edge_type.value} {{branch: $branch, status: "active"}}]->({{uuid: $peer_id}})
RETURN e.to IS NULL AS is_open
""",
        params={
            "node_id": person.id,
            "branch": default_branch.name,
            "peer_id": peer_ids[test_case.peer_name],
        },
    )
    assert sorted(record["is_open"] for record in records) == [False, True]

    plan = await DeleteDuplicatedEdgesPatchQuery(db=db).plan()

    assert plan.edges_to_update == []
    assert plan.edges_to_delete == []

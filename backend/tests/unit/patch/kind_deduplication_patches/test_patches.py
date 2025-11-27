import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from infrahub.cli.db import load_export
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

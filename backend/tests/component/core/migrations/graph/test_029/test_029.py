from pathlib import Path

import pytest

from infrahub.cli.db import load_export
from infrahub.core.migrations.graph.m029_duplicates_cleanup import Migration029
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships
from tests.db_snapshot import DbSnapshotterDeduplicated
from tests.helpers.db_validation import verify_no_duplicate_paths


class TestMigration029:
    @pytest.fixture(scope="class", autouse=True)
    async def load_bad_data(self, db: InfrahubDatabase) -> None:
        await delete_all_nodes(db=db)
        export_dir = Path(__file__).parent / ("data_export")
        await load_export(db=db, export_dir=export_dir)
        # export does not include Branches and we need them for the migration
        query = """
CREATE (:Branch {name: "main", is_default: TRUE, is_global: FALSE, branched_from: "2025-02-24T13:12:02.268631Z"})
CREATE (:Branch {name: "-global-", is_default: FALSE, is_global: TRUE, branched_from: "2025-02-24T13:12:02.268631Z"})
CREATE (:Branch {name: "branch-1505", is_default: FALSE, is_global: FALSE, branched_from: "2025-05-15T12:10:00.000000Z"})
CREATE (:Branch {name: "branch-8376", is_default: FALSE, is_global: FALSE, branched_from: "2025-04-25T09:45:00.000000Z"})
CREATE (:Branch {name: "branch-1396", is_default: FALSE, is_global: FALSE, branched_from: "2025-04-29T09:16:30.000000Z"})
CREATE (:Branch {name: "branch-9176", is_default: FALSE, is_global: FALSE, branched_from: "2025-05-01T10:30:00.000000Z"})
        """
        await db.execute_query(query=query)
        # export does not include AttributeValue.value or Boolean.value, we need to set those for the snapshot
        query = """
CALL () {
    MATCH (a:AttributeValue)
    RETURN a
    UNION
    MATCH (a:Boolean)
    RETURN a
}
%(uuid_generation)s
        """ % {"uuid_generation": db.render_uuid_generation(node_label="a", node_attr="value")}
        await db.execute_query(query=query)

    @pytest.mark.skip("Flaky, migration is already released")
    async def test_migration_029(self, db: InfrahubDatabase) -> None:
        snapshotter = DbSnapshotterDeduplicated(db=db)
        before_snapshot = await snapshotter.snapshot()

        migration = Migration029()
        migration.limit = 33
        execution_result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not execution_result.errors

        await verify_no_duplicate_paths(db=db)
        await verify_no_duplicate_relationships(db=db)
        after_snapshot = await snapshotter.snapshot()

        before_snapshot.assert_equal(other=after_snapshot)

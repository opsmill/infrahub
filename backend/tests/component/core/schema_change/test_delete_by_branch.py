from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.schema_change.constants import SchemaChangeEdgeType, SchemaChangeMigrationStatus, SchemaChangeStatus
from infrahub.core.schema_change.models import (
    SchemaChange,
    SchemaChangeApplication,
    SchemaChangeMigration,
    SchemaChangeOperation,
)
from tests.adapters.log import FakeLogger
from tests.helpers.schema_change import (
    BranchHistorySeed,
    MigrationSeed,
    SeededSchemaChangeHistory,
    StoredSchemaChangeRecord,
    attribute_migration,
    count_schema_change_records,
    read_branch_schema_change_records,
    seed_schema_change_history,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

MAIN = "main"
DELETED_BRANCH = "branch-to-delete"
OTHER_BRANCH = "branch-to-keep"
BATCH_SIZE = 5
NBR_DELETED_BRANCH_CHANGES = 2 * BATCH_SIZE + 1
"""Two full batches and one more schema change, so that the deletion needs a third, partial batch."""

DELETION_LOG = f"Deleted {NBR_DELETED_BRANCH_CHANGES} schema change(s) of branch '{DELETED_BRANCH}' with their records"

FAILED_POSITION = 2
NBR_OPERATIONS = 3
MIGRATIONS = (
    MigrationSeed(
        migration=attribute_migration(), status=SchemaChangeMigrationStatus.APPLIED, nbr_migrations_executed=1
    ),
    MigrationSeed(migration=attribute_migration(migration_name="attribute.kind.update", field_name="name")),
)


@dataclass(frozen=True)
class DeletionContext:
    history: SeededSchemaChangeHistory
    main_parent_id: str
    records_before: dict[str, dict[str, StoredSchemaChangeRecord]]
    """The records of each branch before the deletion, by UUID."""

    deleter: BranchDataDeleter
    log: FakeLogger


def _labels(records: dict[str, StoredSchemaChangeRecord]) -> Counter[str]:
    return Counter(record.label for record in records.values())


def _expected_labels(nbr_schema_changes: int) -> Counter[str]:
    return Counter(
        {
            SchemaChange.get_type(): nbr_schema_changes,
            SchemaChangeOperation.get_type(): nbr_schema_changes * NBR_OPERATIONS,
            SchemaChangeApplication.get_type(): nbr_schema_changes,
            SchemaChangeMigration.get_type(): nbr_schema_changes * len(MIGRATIONS),
        }
    )


class TestDeleteSchemaChangesByBranch:
    """Deletes the schema change records of one branch in batches, and leaves those of the other branches.

    The methods run in the order they are defined; the deletion happens in the second one.
    """

    @pytest.fixture(scope="class")
    async def context(self, db: InfrahubDatabase, empty_database_scope_class: None) -> DeletionContext:
        main_history = await seed_schema_change_history(
            db=db,
            branches=[
                BranchHistorySeed(
                    branch=MAIN,
                    changes=[SchemaChangeStatus.APPLIED, SchemaChangeStatus.APPLIED],
                    nbr_operations=NBR_OPERATIONS,
                    migrations=MIGRATIONS,
                )
            ],
        )
        main_parent_id = main_history.applied_on_branch(MAIN)[-1].id
        deleted_branch_changes = [SchemaChangeStatus.APPLIED] * NBR_DELETED_BRANCH_CHANGES
        deleted_branch_changes[FAILED_POSITION] = SchemaChangeStatus.FAILED
        branch_history = await seed_schema_change_history(
            db=db,
            branches=[
                BranchHistorySeed(
                    branch=DELETED_BRANCH,
                    changes=deleted_branch_changes,
                    nbr_operations=NBR_OPERATIONS,
                    migrations=MIGRATIONS,
                    first_version=3,
                    first_parent_id=main_parent_id,
                ),
                BranchHistorySeed(
                    branch=OTHER_BRANCH,
                    changes=[SchemaChangeStatus.APPLIED, SchemaChangeStatus.FAILED],
                    nbr_operations=NBR_OPERATIONS,
                    migrations=MIGRATIONS,
                    first_version=3,
                    first_parent_id=main_parent_id,
                ),
            ],
        )
        log = FakeLogger()
        return DeletionContext(
            history=SeededSchemaChangeHistory(
                schema_changes=main_history.schema_changes + branch_history.schema_changes
            ),
            main_parent_id=main_parent_id,
            records_before={
                branch: await read_branch_schema_change_records(db=db, branch=branch)
                for branch in (MAIN, DELETED_BRANCH, OTHER_BRANCH)
            },
            deleter=BranchDataDeleter(db=db, batch_size=BATCH_SIZE, log=log),
            log=log,
        )

    async def test_records_before_the_deletion_are_the_seeded_ones(self, context: DeletionContext) -> None:
        for branch, nbr_schema_changes in ((MAIN, 2), (DELETED_BRANCH, NBR_DELETED_BRANCH_CHANGES), (OTHER_BRANCH, 2)):
            records = context.records_before[branch]
            assert _labels(records) == _expected_labels(nbr_schema_changes)
            assert {uuid for uuid, record in records.items() if record.label == SchemaChange.get_type()} == {
                change.id for change in context.history.on_branch(branch)
            }

        deleted_branch_records = context.records_before[DELETED_BRANCH]
        failed_change = context.history.on_branch(DELETED_BRANCH)[FAILED_POSITION]
        assert deleted_branch_records[failed_change.id].properties["status"] == SchemaChangeStatus.FAILED.value
        main_parent_db_id = context.records_before[MAIN][context.main_parent_id].db_id
        first_change = context.history.on_branch(DELETED_BRANCH)[0]
        assert [
            edge
            for edge in deleted_branch_records[first_change.id].edges
            if edge[0] == SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value
        ] == [(SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value, main_parent_db_id)]

    async def test_deletion_removes_every_record_of_the_branch(
        self, db: InfrahubDatabase, context: DeletionContext
    ) -> None:
        edges_removed = await context.deleter.delete_branch_data(branch_name=DELETED_BRANCH)

        assert edges_removed == 0
        assert context.log.info_logs == [DELETION_LOG]
        assert await read_branch_schema_change_records(db=db, branch=DELETED_BRANCH) == {}
        assert await count_schema_change_records(db=db, uuids=list(context.records_before[DELETED_BRANCH])) == 0
        assert await count_schema_change_records(db=db) == len(context.records_before[MAIN]) + len(
            context.records_before[OTHER_BRANCH]
        )

    async def test_records_of_main_and_of_the_other_branch_are_unchanged(
        self, db: InfrahubDatabase, context: DeletionContext
    ) -> None:
        assert await read_branch_schema_change_records(db=db, branch=MAIN) == context.records_before[MAIN]
        assert (
            await read_branch_schema_change_records(db=db, branch=OTHER_BRANCH) == context.records_before[OTHER_BRANCH]
        )

    async def test_second_deletion_deletes_nothing(self, db: InfrahubDatabase, context: DeletionContext) -> None:
        edges_removed = await context.deleter.delete_branch_data(branch_name=DELETED_BRANCH)

        assert edges_removed == 0
        assert context.log.info_logs == [DELETION_LOG]
        assert await read_branch_schema_change_records(db=db, branch=MAIN) == context.records_before[MAIN]
        assert (
            await read_branch_schema_change_records(db=db, branch=OTHER_BRANCH) == context.records_before[OTHER_BRANCH]
        )

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
)
from infrahub.core.schema_change.history_reader import SchemaChangeHistoryPage, SchemaChangeHistoryReader
from tests.helpers.schema_change import (
    SEEDED_FAILURE_ERROR,
    BranchHistorySeed,
    MigrationSeed,
    SeededSchemaChangeHistory,
    attribute_migration,
    seed_schema_change_history,
    seeded_operation_value,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

MAIN = "main"
BRANCH_WITH_CHANGES = "branch-with-changes"
BRANCH_WITH_RUNNING_CHANGE = "branch-with-running-change"
NBR_OPERATIONS = 7
OPERATIONS_PAGE_SIZE = 3
MIGRATION_ERROR = "The migration found an attribute it cannot convert"


def _ids(page: SchemaChangeHistoryPage) -> list[str]:
    return [str(entry.schema_change.uuid) for entry in page.entries]


@pytest.fixture(scope="class")
async def seeded_history(db: InfrahubDatabase, empty_database_scope_class: None) -> SeededSchemaChangeHistory:
    main_history = await seed_schema_change_history(
        db=db,
        branches=[
            BranchHistorySeed(
                branch=MAIN,
                changes=[
                    SchemaChangeStatus.APPLIED,
                    SchemaChangeStatus.FAILED,
                    SchemaChangeStatus.APPLIED,
                    SchemaChangeStatus.RUNNING,
                    SchemaChangeStatus.APPLIED,
                ],
                nbr_operations=NBR_OPERATIONS,
                migrations=[
                    MigrationSeed(
                        migration=attribute_migration(),
                        status=SchemaChangeMigrationStatus.APPLIED,
                        nbr_migrations_executed=0,
                    ),
                    MigrationSeed(
                        migration=attribute_migration(migration_name="attribute.kind.update", field_name="name"),
                        status=SchemaChangeMigrationStatus.FAILED,
                        errors=(MIGRATION_ERROR,),
                    ),
                    MigrationSeed(migration=attribute_migration(field_name="description")),
                ],
            )
        ],
    )
    last_main_change = main_history.applied_on_branch(MAIN)[-1]
    branch_history = await seed_schema_change_history(
        db=db,
        branches=[
            BranchHistorySeed(
                branch=BRANCH_WITH_CHANGES,
                changes=[SchemaChangeStatus.FAILED, SchemaChangeStatus.APPLIED, SchemaChangeStatus.APPLIED],
                first_version=4,
                first_parent_id=last_main_change.id,
            ),
            BranchHistorySeed(
                branch=BRANCH_WITH_RUNNING_CHANGE, changes=[SchemaChangeStatus.RUNNING], nbr_operations=NBR_OPERATIONS
            ),
        ],
    )
    return SeededSchemaChangeHistory(schema_changes=main_history.schema_changes + branch_history.schema_changes)


class TestSchemaChangeHistoryReader:
    async def test_list_returns_applied_by_version_then_the_others_by_creation(
        self, db: InfrahubDatabase, seeded_history: SeededSchemaChangeHistory
    ) -> None:
        applied_1, failed, applied_2, running, applied_3 = seeded_history.on_branch(MAIN)

        page = await SchemaChangeHistoryReader(db=db).list_schema_changes(branch=MAIN, limit=10, offset=0)

        assert page.count == 5
        assert _ids(page) == [applied_1.id, applied_2.id, applied_3.id, failed.id, running.id]
        assert [
            (
                entry.schema_change.status,
                entry.schema_change.version,
                str(entry.parent.uuid) if entry.parent else None,
                entry.schema_change.applied_at,
            )
            for entry in page.entries
        ] == [
            (SchemaChangeStatus.APPLIED, 1, None, applied_1.at.to_string()),
            (SchemaChangeStatus.APPLIED, 2, applied_1.id, applied_2.at.to_string()),
            (SchemaChangeStatus.APPLIED, 3, applied_2.id, applied_3.at.to_string()),
            (SchemaChangeStatus.FAILED, None, None, None),
            (SchemaChangeStatus.RUNNING, None, None, None),
        ]

    async def test_list_pages_with_limit_and_offset_and_counts_all_pages(
        self, db: InfrahubDatabase, seeded_history: SeededSchemaChangeHistory
    ) -> None:
        _, failed, _, running, applied_3 = seeded_history.on_branch(MAIN)
        reader = SchemaChangeHistoryReader(db=db)

        middle_page = await reader.list_schema_changes(branch=MAIN, limit=2, offset=2)
        last_page = await reader.list_schema_changes(branch=MAIN, limit=2, offset=4)

        assert (middle_page.count, _ids(middle_page)) == (5, [applied_3.id, failed.id])
        assert (last_page.count, _ids(last_page)) == (5, [running.id])

    async def test_list_filters_by_status(
        self, db: InfrahubDatabase, seeded_history: SeededSchemaChangeHistory
    ) -> None:
        _, failed, _, running, _ = seeded_history.on_branch(MAIN)

        page = await SchemaChangeHistoryReader(db=db).list_schema_changes(
            branch=MAIN, limit=10, offset=0, statuses=[SchemaChangeStatus.FAILED, SchemaChangeStatus.RUNNING]
        )

        assert (page.count, _ids(page)) == (2, [failed.id, running.id])

    async def test_list_returns_the_schema_changes_of_the_branch_only(
        self, db: InfrahubDatabase, seeded_history: SeededSchemaChangeHistory
    ) -> None:
        failed, applied_4, applied_5 = seeded_history.on_branch(BRANCH_WITH_CHANGES)
        last_main_change = seeded_history.applied_on_branch(MAIN)[-1]
        reader = SchemaChangeHistoryReader(db=db)

        page = await reader.list_schema_changes(branch=BRANCH_WITH_CHANGES, limit=10, offset=0)
        running_page = await reader.list_schema_changes(branch=BRANCH_WITH_RUNNING_CHANGE, limit=10, offset=0)

        assert (page.count, _ids(page)) == (3, [applied_4.id, applied_5.id, failed.id])
        assert [
            (entry.schema_change.branch, entry.schema_change.version, entry.parent.branch if entry.parent else None)
            for entry in page.entries
        ] == [
            (BRANCH_WITH_CHANGES, 4, MAIN),
            (BRANCH_WITH_CHANGES, 5, BRANCH_WITH_CHANGES),
            (BRANCH_WITH_CHANGES, None, None),
        ]
        assert page.entries[0].parent is not None
        assert str(page.entries[0].parent.uuid) == last_main_change.id
        assert page.entries[0].parent.version == 3
        assert (running_page.count, _ids(running_page)) == (
            1,
            [seeded_history.on_branch(BRANCH_WITH_RUNNING_CHANGE)[0].id],
        )

    async def test_operations_come_in_pages_with_the_count_of_each_schema_change(
        self, db: InfrahubDatabase, seeded_history: SeededSchemaChangeHistory
    ) -> None:
        main_change = seeded_history.on_branch(MAIN)[0]
        running_branch_change = seeded_history.on_branch(BRANCH_WITH_RUNNING_CHANGE)[0]
        schema_change_ids = [main_change.id, running_branch_change.id]
        reader = SchemaChangeHistoryReader(db=db)

        second_pages = await reader.list_operations(
            schema_change_ids=schema_change_ids, limit=OPERATIONS_PAGE_SIZE, offset=OPERATIONS_PAGE_SIZE
        )
        last_pages = await reader.list_operations(
            schema_change_ids=schema_change_ids, limit=OPERATIONS_PAGE_SIZE, offset=2 * OPERATIONS_PAGE_SIZE
        )

        assert sorted(second_pages) == sorted(schema_change_ids)
        for schema_change_id in schema_change_ids:
            assert second_pages[schema_change_id].count == NBR_OPERATIONS
            assert [
                (stored.position, stored.operation.value) for stored in second_pages[schema_change_id].operations
            ] == [(3, seeded_operation_value(3)), (4, seeded_operation_value(4)), (5, seeded_operation_value(5))]
            assert last_pages[schema_change_id].count == NBR_OPERATIONS
            assert [
                (stored.position, stored.operation.value) for stored in last_pages[schema_change_id].operations
            ] == [(6, seeded_operation_value(6))]

    async def test_applications_come_with_their_migration_records(
        self, db: InfrahubDatabase, seeded_history: SeededSchemaChangeHistory
    ) -> None:
        applied_1, failed, *_ = seeded_history.on_branch(MAIN)

        applications = await SchemaChangeHistoryReader(db=db).list_applications(
            schema_change_ids=[applied_1.id, failed.id]
        )

        assert sorted(applications) == sorted([applied_1.id, failed.id])
        assert [
            (str(record.application.uuid), record.application.status, record.application.branch, record.application.at)
            for record in applications[applied_1.id]
        ] == [(applied_1.application_id, SchemaChangeApplicationStatus.APPLIED, MAIN, applied_1.at.to_string())]
        assert applications[applied_1.id][0].application.error is None
        assert [
            (
                migration.position,
                migration.migration_name,
                migration.field_name,
                migration.status,
                migration.nbr_migrations_executed,
                migration.errors,
            )
            for migration in applications[applied_1.id][0].migrations
        ] == [
            (0, "node.attribute.add", "color", SchemaChangeMigrationStatus.APPLIED, 0, []),
            (1, "attribute.kind.update", "name", SchemaChangeMigrationStatus.FAILED, None, [MIGRATION_ERROR]),
            (2, "node.attribute.add", "description", SchemaChangeMigrationStatus.WAITING, None, []),
        ]
        assert [
            (str(record.application.uuid), record.application.status, record.application.error)
            for record in applications[failed.id]
        ] == [(failed.application_id, SchemaChangeApplicationStatus.FAILED, SEEDED_FAILURE_ERROR)]
        assert [migration.status for migration in applications[failed.id][0].migrations] == [
            SchemaChangeMigrationStatus.ROLLED_BACK,
            SchemaChangeMigrationStatus.FAILED,
            SchemaChangeMigrationStatus.WAITING,
        ]

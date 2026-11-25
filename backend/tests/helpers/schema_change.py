from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import SYSTEM_USER_ID, SchemaPathType
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema_change.constants import (
    SCHEMA_CHANGE_APPLICATIONS_MAX_LIMIT,
    SCHEMA_CHANGE_MIGRATIONS_MAX_LIMIT,
)
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeEdgeType,
    SchemaChangeMigrationStatus,
    SchemaChangeRecordLabel,
    SchemaChangeStatus,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.factory import build_schema_change_history_reader, build_schema_change_repository
from infrahub.core.schema_change.models import SchemaChangeApplication
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.schema_change.record_serializer import SchemaChangeRecordSerializer
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.schema_change.models import SchemaChangeMigration
    from infrahub.core.schema_change.repository import SchemaChangeRepository
    from infrahub.database import InfrahubDatabase

SEEDED_OPERATION_KIND = "TestCar"
SEEDED_OPERATION_ELEMENT = "color"
SEEDED_OPERATION_PROPERTY = "label"
SEEDED_FAILURE_ERROR = "The migration node.attribute.add failed on 2 nodes"
SEEDED_SUMMARY = "testcar_color_update"
"""The summary of a seeded schema change with one operation; `_and_<n>_more` follows when it has more."""

SCHEMA_CHANGE_RECORD_LABEL_EXPRESSION = "|".join(label.value for label in SchemaChangeRecordLabel)


def seeded_operation_value(position: int) -> str:
    return f"Color {position}"


def build_seeded_operations(nbr_operations: int) -> list[SchemaOperation]:
    """Return operations that each change the label of one attribute, told apart by their value."""
    return [
        SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=SEEDED_OPERATION_KIND,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name=SEEDED_OPERATION_ELEMENT,
            property_name=SEEDED_OPERATION_PROPERTY,
            value=seeded_operation_value(position),
            previous_value=seeded_operation_value(position - 1),
        )
        for position in range(nbr_operations)
    ]


def attribute_migration(
    *, migration_name: str = "node.attribute.add", kind: str = "TestCar", field_name: str = "color"
) -> SchemaUpdateMigrationInfo:
    return SchemaUpdateMigrationInfo(
        migration_name=migration_name,
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=field_name),
    )


@dataclass(frozen=True)
class MigrationSeed:
    """One migration of an application, and the status its record ends with."""

    migration: SchemaUpdateMigrationInfo
    status: SchemaChangeMigrationStatus = SchemaChangeMigrationStatus.WAITING
    nbr_migrations_executed: int | None = None
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class BranchHistorySeed:
    """The schema changes to create on one branch, in the order they are created."""

    branch: str
    changes: Sequence[SchemaChangeStatus]
    """`applied`, `failed` or `running`, one item for each schema change."""

    nbr_operations: int = 1
    migrations: Sequence[MigrationSeed] = ()
    """The migrations of the application of each schema change of the branch."""

    first_version: int = 1
    """The version of the first applied schema change; the next applied ones follow it."""

    first_parent_id: str | None = None
    """The parent of the first applied schema change, such as one of main for a branch."""


@dataclass(frozen=True)
class SeededSchemaChange:
    id: str
    application_id: str
    branch: str
    status: SchemaChangeStatus
    version: int | None
    parent_id: str | None
    at: Timestamp
    """The timestamp of the application, which is also `applied_at` for an applied schema change."""

    operations: list[SchemaOperation]


@dataclass(frozen=True)
class SeededSchemaChangeHistory:
    schema_changes: list[SeededSchemaChange] = field(default_factory=list)
    """In the order they were created."""

    def on_branch(self, branch: str) -> list[SeededSchemaChange]:
        return [change for change in self.schema_changes if change.branch == branch]

    def applied_on_branch(self, branch: str) -> list[SeededSchemaChange]:
        return [change for change in self.on_branch(branch) if change.status == SchemaChangeStatus.APPLIED]


async def seed_schema_change_history(
    *, db: InfrahubDatabase, branches: Sequence[BranchHistorySeed], user_id: str = SYSTEM_USER_ID
) -> SeededSchemaChangeHistory:
    """Create schema changes, their applications and their migration records through the repository.

    The branches are seeded in the order given. An applied schema change gets the next version of
    its branch and the applied schema change before it as its parent. A failed schema change gets
    `SEEDED_FAILURE_ERROR`, after its migration records got their statuses, so a record seeded as
    `applied` becomes `rolled_back`.

    Raises:
        ValueError: When a branch seed asks for a status that a load does not leave.

    """
    repository = build_schema_change_repository(db=db)
    seeded: list[SeededSchemaChange] = []

    for branch_seed in branches:
        next_version = branch_seed.first_version
        parent_id = branch_seed.first_parent_id
        for status in branch_seed.changes:
            operations = build_seeded_operations(nbr_operations=branch_seed.nbr_operations)
            at = Timestamp()
            created = await repository.create_schema_change(
                branch=branch_seed.branch, operations=operations, at=at, user_id=user_id
            )
            await _seed_migrations(
                repository=repository, application_id=created.application_id, migrations=branch_seed.migrations
            )

            version: int | None = None
            change_parent_id: str | None = None
            match status:
                case SchemaChangeStatus.APPLIED:
                    version = next_version
                    change_parent_id = parent_id
                    await repository.mark_applied(
                        schema_change_id=created.schema_change_id,
                        application_id=created.application_id,
                        version=version,
                        parent_id=change_parent_id,
                        applied_at=at,
                        user_id=user_id,
                    )
                    next_version += 1
                    parent_id = created.schema_change_id
                case SchemaChangeStatus.FAILED:
                    await repository.mark_failed(
                        schema_change_id=created.schema_change_id,
                        application_id=created.application_id,
                        error=SEEDED_FAILURE_ERROR,
                        user_id=user_id,
                    )
                case SchemaChangeStatus.RUNNING:
                    pass
                case SchemaChangeStatus.STAGED:
                    raise ValueError(f"A schema change cannot be seeded with the status {status.value}")

            seeded.append(
                SeededSchemaChange(
                    id=created.schema_change_id,
                    application_id=created.application_id,
                    branch=branch_seed.branch,
                    status=status,
                    version=version,
                    parent_id=change_parent_id,
                    at=at,
                    operations=operations,
                )
            )

    return SeededSchemaChangeHistory(schema_changes=seeded)


async def _seed_migrations(
    *, repository: SchemaChangeRepository, application_id: str, migrations: Sequence[MigrationSeed]
) -> None:
    if not migrations:
        return

    await repository.create_migration_records(
        application_id=application_id, migrations=[seed.migration for seed in migrations]
    )
    for position, seed in enumerate(migrations):
        if seed.status == SchemaChangeMigrationStatus.WAITING:
            continue
        await repository.set_migration_records_status(
            application_id=application_id,
            positions=[position],
            status=seed.status,
            nbr_migrations_executed=seed.nbr_migrations_executed,
            errors=list(seed.errors),
        )


async def seed_application(
    *,
    db: InfrahubDatabase,
    schema_change_id: str,
    branch: str,
    status: SchemaChangeApplicationStatus,
    at: Timestamp,
    user_id: str = SYSTEM_USER_ID,
) -> str:
    """Add an application to a stored schema change, as applying it to one more branch would, and return its ID."""
    created_at = Timestamp().to_string()
    application = SchemaChangeApplication(
        uuid=str(UUIDT()),
        branch=branch,
        status=status,
        at=at.to_string(),
        created_at=created_at,
        created_by=user_id,
        updated_at=created_at,
        updated_by=user_id,
    )
    await db.execute_query(
        query=f"""
        MATCH (schema_change:{SchemaChangeRecordLabel.SCHEMA_CHANGE.value} {{uuid: $schema_change_id}})
        CREATE (application:{SchemaChangeRecordLabel.APPLICATION.value} $application)
        CREATE (schema_change)-[:{SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value}]->(application)
        """,
        params={
            "schema_change_id": schema_change_id,
            "application": SchemaChangeRecordSerializer().application_to_properties(record=application),
        },
        name="test_seed_schema_change_application",
    )
    return application.uuid


@dataclass(frozen=True)
class ApplicationWithMigrations:
    application: SchemaChangeApplication
    migrations: list[SchemaChangeMigration]


async def read_applications_with_migrations(
    *, db: InfrahubDatabase, schema_change_ids: Sequence[str]
) -> dict[str, list[ApplicationWithMigrations]]:
    """Return every application of each schema change with all its migration records, read in the largest pages."""
    reader = build_schema_change_history_reader(db=db)
    application_pages = await reader.list_applications(
        schema_change_ids=schema_change_ids, limit=SCHEMA_CHANGE_APPLICATIONS_MAX_LIMIT, offset=0
    )
    application_ids = [application.uuid for page in application_pages.values() for application in page.applications]
    migration_pages = await reader.list_migrations(
        application_ids=application_ids, limit=SCHEMA_CHANGE_MIGRATIONS_MAX_LIMIT, offset=0
    )
    return {
        schema_change_id: [
            ApplicationWithMigrations(application=application, migrations=migration_pages[application.uuid].migrations)
            for application in page.applications
        ]
        for schema_change_id, page in application_pages.items()
    }


@dataclass(frozen=True)
class StoredSchemaChangeRecord:
    """One record vertex as the database holds it."""

    labels: tuple[str, ...]
    properties: dict[str, object]
    edges: tuple[tuple[str, str], ...]
    """Each edge that leaves the record, as its type and the `uuid` of its end, sorted."""


async def read_branch_schema_change_records(
    *, db: InfrahubDatabase, branch: str
) -> dict[str, StoredSchemaChangeRecord]:
    """Return the schema changes of a branch and every operation, application and migration record under them, by UUID."""
    results = await db.execute_query(
        query=f"""
        MATCH (schema_change:{SchemaChangeRecordLabel.SCHEMA_CHANGE.value} {{branch: $branch}})
        OPTIONAL MATCH (schema_change)-[:{SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value}]->(operation)
        OPTIONAL MATCH (schema_change)-[:{SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value}]->(application)
        OPTIONAL MATCH (application)-[:{SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value}]->(migration)
        UNWIND [schema_change, operation, application, migration] AS record
        WITH DISTINCT record
        WHERE record IS NOT NULL
        RETURN record.uuid AS uuid, labels(record) AS labels, properties(record) AS properties,
            [(record)-[edge]->(peer) | [type(edge), peer.uuid]] AS edges
        """,
        params={"branch": branch},
        name="test_schema_change_records_of_branch",
    )
    return {
        str(result.get("uuid")): StoredSchemaChangeRecord(
            labels=tuple(sorted(str(label) for label in result.get("labels"))),
            properties=dict(result.get("properties")),
            edges=tuple(sorted((str(edge_type), str(peer_id)) for edge_type, peer_id in result.get("edges"))),
        )
        for result in results
    }


async def count_schema_change_records(*, db: InfrahubDatabase, uuids: Sequence[str] | None = None) -> int:
    """Count the record vertices of every branch, or only those with one of the UUIDs given."""
    results = await db.execute_query(
        query=f"""
        MATCH (record:{SCHEMA_CHANGE_RECORD_LABEL_EXPRESSION})
        WHERE $uuids IS NULL OR record.uuid IN $uuids
        RETURN count(record) AS nbr_records
        """,
        params={"uuids": list(uuids) if uuids is not None else None},
        name="test_count_schema_change_records",
    )
    return int(results[0].get("nbr_records"))


async def count_schema_change_record_edges_to_root(*, db: InfrahubDatabase) -> int:
    """Count the edges between a record vertex and the root vertex, in either direction."""
    results = await db.execute_query(
        query=f"""
        MATCH (record:{SCHEMA_CHANGE_RECORD_LABEL_EXPRESSION})-[edge]-(:Root)
        RETURN count(edge) AS nbr_edges
        """,
        name="test_count_schema_change_record_edges_to_root",
    )
    return int(results[0].get("nbr_edges"))

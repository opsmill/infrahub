from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.schema_change.application_migration_recorder import ApplicationMigrationRecorder
from infrahub.core.schema_change.application_runner import SchemaChangeApplicationRunner
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.candidate import SchemaCandidateBuilder
from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
from infrahub.core.schema_change.migration_recorder import MigrationRecorder, NoRecordMigrationRecorder
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from infrahub.core.schema_change.recorder import SchemaChangeRecorder
from infrahub.core.schema_change.repository import SchemaChangeRepository
from infrahub.core.schema_change.version_resolver import SchemaChangeVersionResolver

if TYPE_CHECKING:
    from infrahub.core.schema_change.application_runner import SchemaUpdateExecutor
    from infrahub.database import InfrahubDatabase


def build_schema_candidate_builder() -> SchemaCandidateBuilder:
    return SchemaCandidateBuilder(
        operation_builder=SchemaOperationBuilder(), applier=SchemaChangeApplier(), comparer=SchemaCandidateComparer()
    )


def build_schema_change_recorder(db: InfrahubDatabase, default_branch_name: str) -> SchemaChangeRecorder:
    repository = SchemaChangeRepository(db=db)
    return SchemaChangeRecorder(
        repository=repository,
        version_resolver=SchemaChangeVersionResolver(repository=repository, default_branch_name=default_branch_name),
    )


def build_schema_change_application_runner(
    db: InfrahubDatabase, executor: SchemaUpdateExecutor, default_branch_name: str
) -> SchemaChangeApplicationRunner:
    return SchemaChangeApplicationRunner(
        recorder=build_schema_change_recorder(db=db, default_branch_name=default_branch_name), executor=executor
    )


def build_migration_recorder(db: InfrahubDatabase, application_id: str | None) -> MigrationRecorder:
    if application_id is None:
        return NoRecordMigrationRecorder()
    return ApplicationMigrationRecorder(store=SchemaChangeRepository(db=db), application_id=application_id)

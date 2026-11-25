from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import typer

import infrahub.core.migrations.schema.tasks as tasks_module
from infrahub import lock
from infrahub.cli.db import CoreSchemaStatus, check_core_schema_diff, update_core_schema
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, BranchSupportType
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.candidate import SchemaCandidateBuilder
from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
from infrahub.core.schema_change.enums import SchemaChangeEdgeType, SchemaChangeRecordLabel, SchemaChangeSource
from infrahub.core.schema_change.factory import build_schema_candidate_builder, build_schema_change_recorder
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder, SchemaOperationBuildResult
from infrahub.core.timestamp import Timestamp
from infrahub.lock import UninitializedLockRegistry
from tests.helpers.schema_change import (
    StoredSchemaChangeRecord,
    build_seeded_operations,
    count_schema_change_records,
    read_branch_schema_change_records,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query import MigrationBaseQuery
    from infrahub.core.schema import NodeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

TAG_KIND = "BuiltinTag"
ADDED_ATTRIBUTE = "description"
MIGRATION_FAILURE = "The description of the tags could not be added"
UNEXPECTED_FAILURE = "The operation builder failed [type=unexpected] in a way it does not document [/note]"
MISMATCH_REPORT = (
    "Unable to update the schema: The schema change cannot be built accurately, so the request was not completed. "
    "This is an error in Infrahub, not in the schema file: the operations built from the file do not rebuild its "
    "schema for the kinds BuiltinTag."
)


@dataclass(frozen=True)
class MainRecords:
    """The records of main, by label."""

    schema_changes: list[StoredSchemaChangeRecord]
    operations: list[StoredSchemaChangeRecord]
    applications: list[StoredSchemaChangeRecord]
    migrations: list[StoredSchemaChangeRecord]


async def _read_main_records(db: InfrahubDatabase) -> MainRecords:
    records = list((await read_branch_schema_change_records(db=db, branch=registry.default_branch)).values())

    def with_label(label: SchemaChangeRecordLabel) -> list[StoredSchemaChangeRecord]:
        return [record for record in records if label.value in record.labels]

    return MainRecords(
        schema_changes=with_label(SchemaChangeRecordLabel.SCHEMA_CHANGE),
        operations=with_label(SchemaChangeRecordLabel.OPERATION),
        applications=with_label(SchemaChangeRecordLabel.APPLICATION),
        migrations=with_label(SchemaChangeRecordLabel.MIGRATION),
    )


@dataclass(frozen=True)
class OlderDatabase:
    """A database from an older release whose main already holds one schema change of a user."""

    user_change_id: str


def _console_text(capsys: pytest.CaptureFixture[str]) -> str:
    # The migration console wraps long lines, so the words are compared without the line breaks.
    return " ".join(capsys.readouterr().out.split())


def _make_tag_older(schema_branch: SchemaBranch) -> None:
    # The tag kind has no description yet, and is stored branch agnostic, which the core models change to aware.
    tag = schema_branch.get(name=TAG_KIND)
    tag.attributes = [attribute for attribute in tag.attributes if attribute.name != ADDED_ATTRIBUTE]
    tag.branch = BranchSupportType.AGNOSTIC
    schema_branch.set(name=TAG_KIND, schema=tag)


async def _stored_tag(db: InfrahubDatabase, branch: Branch) -> NodeSchema:
    stored = await registry.schema.load_schema_from_db(db=db, branch=branch)
    return stored.get_node(name=TAG_KIND, duplicate=False)


async def _assert_tag_is_as_before(db: InfrahubDatabase, branch: Branch) -> None:
    tag = await _stored_tag(db=db, branch=branch)
    assert (ADDED_ATTRIBUTE in tag.attribute_names, tag.branch) == (False, BranchSupportType.AGNOSTIC)


class TagAttributeAddMigrationThatFails(NodeAttributeAddMigration):
    """Fails on the tag kind, and adds the attribute as usual on any other kind."""

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        if self.schema_path.schema_kind == TAG_KIND:
            return MigrationResult(errors=[MIGRATION_FAILURE])
        return await super().execute(migration_input=migration_input, branch=branch, queries=queries)


class DifferingKindComparer(SchemaCandidateComparer):
    """Reports the tag kind as different between the direct load and the applied schema, whatever they hold."""

    def differing_kinds(self, *, direct_load_schema: SchemaBranch, applied_schema: SchemaBranch) -> list[str]:
        return [TAG_KIND]


class OperationBuilderThatFailsUnexpectedly(SchemaOperationBuilder):
    """Raises an error that building operations does not document."""

    def build(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaOperationBuildResult:
        raise RuntimeError(UNEXPECTED_FAILURE)


@pytest.fixture(scope="class")
async def older_database(db: InfrahubDatabase, default_branch_scope_class: Branch) -> OlderDatabase:
    schema_branch = registry.schema.register_schema(
        schema=SchemaRoot(**internal_schema), branch=default_branch_scope_class.name
    )
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.load_schema(schema=SchemaRoot(**deprecated_models))
    _make_tag_older(schema_branch=schema_branch)
    schema_branch.process()
    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch_scope_class, db=db)

    recorder = build_schema_change_recorder(db=db, default_branch_name=registry.default_branch)
    user_change = await recorder.record_applied(
        branch=default_branch_scope_class,
        operations=build_seeded_operations(nbr_operations=1),
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
        source=SchemaChangeSource.USER,
    )
    return OlderDatabase(user_change_id=user_change.schema_change_id)


@pytest.fixture
def failing_tag_attribute_add_migration() -> Generator[None]:
    original_map = tasks_module.MIGRATION_MAP.copy()
    tasks_module.MIGRATION_MAP["node.attribute.add"] = TagAttributeAddMigrationThatFails
    yield
    tasks_module.MIGRATION_MAP.clear()
    tasks_module.MIGRATION_MAP.update(original_map)


@pytest.fixture
def uninitialized_lock_registry() -> Generator[None]:
    """Replace the lock registry with one that raises on any lock, as in a process that never initialized it."""
    original = lock.registry
    lock.registry = UninitializedLockRegistry()
    yield
    lock.registry = original


class TestCoreSchemaUpdate:
    """Each step runs the core schema update on the database that the steps before it left."""

    async def test_step01_check_and_update_report_that_the_operations_do_not_rebuild_the_core_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        older_database: OlderDatabase,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        candidate_builder = SchemaCandidateBuilder(
            operation_builder=SchemaOperationBuilder(), applier=SchemaChangeApplier(), comparer=DifferingKindComparer()
        )

        status = await check_core_schema_diff(db=db, candidate_builder=candidate_builder)
        check_report = _console_text(capsys)
        with pytest.raises(typer.Exit) as exit_info:
            await update_core_schema(db=db, candidate_builder=candidate_builder, initialize=False)
        update_report = _console_text(capsys)

        assert status == CoreSchemaStatus.REFUSED
        assert (MISMATCH_REPORT in check_report, MISMATCH_REPORT in update_report) == (True, True)
        assert exit_info.value.exit_code == 1
        records = await _read_main_records(db=db)
        assert [record.properties["uuid"] for record in records.schema_changes] == [older_database.user_change_id]
        await _assert_tag_is_as_before(db=db, branch=default_branch_scope_class)

    async def test_step02_unexpected_error_building_the_candidate_stops_the_update_and_shows_its_traceback(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        older_database: OlderDatabase,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        candidate_builder = SchemaCandidateBuilder(
            operation_builder=OperationBuilderThatFailsUnexpectedly(),
            applier=SchemaChangeApplier(),
            comparer=SchemaCandidateComparer(),
        )

        with pytest.raises(typer.Exit) as exit_info:
            await update_core_schema(db=db, candidate_builder=candidate_builder, initialize=False)
        report = _console_text(capsys)

        assert exit_info.value.exit_code == 1
        assert (
            f"Unable to update the schema: {UNEXPECTED_FAILURE}" in report,
            "Traceback (most recent call last)" in report,
            f"RuntimeError: {UNEXPECTED_FAILURE}" in report,
        ) == (True, True, True)
        records = await _read_main_records(db=db)
        assert [record.properties["uuid"] for record in records.schema_changes] == [older_database.user_change_id]
        await _assert_tag_is_as_before(db=db, branch=default_branch_scope_class)

    async def test_step03_failed_migration_leaves_a_failed_schema_change_and_the_schema_as_before(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        older_database: OlderDatabase,
        failing_tag_attribute_add_migration: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with pytest.raises(typer.Exit) as exit_info:
            await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        assert exit_info.value.exit_code == 1
        assert f"Schema update failed: {MIGRATION_FAILURE}" in _console_text(capsys)
        records = await _read_main_records(db=db)
        [failed] = [
            record for record in records.schema_changes if record.properties["uuid"] != older_database.user_change_id
        ]
        assert {key: failed.properties.get(key) for key in ("status", "version", "source")} == {
            "status": "failed",
            "version": None,
            "source": "core_schema_update",
        }
        [application] = [record for record in records.applications if record.properties["status"] == "failed"]
        assert application.properties["error"] == MIGRATION_FAILURE
        assert [record.properties["status"] for record in records.migrations] == ["failed"]
        await _assert_tag_is_as_before(db=db, branch=default_branch_scope_class)

    async def test_step04_check_reports_that_the_core_schema_needs_an_update(
        self, db: InfrahubDatabase, older_database: OlderDatabase, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status = await check_core_schema_diff(db=db, candidate_builder=build_schema_candidate_builder())

        assert status == CoreSchemaStatus.UPDATE_REQUIRED
        assert "Unable to update the schema" not in _console_text(capsys)

    async def test_step05_update_stores_the_next_applied_schema_change_of_main_without_taking_a_lock(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        older_database: OlderDatabase,
        uninitialized_lock_registry: None,
    ) -> None:
        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        records = await _read_main_records(db=db)
        by_status = {
            record.properties["status"]: record
            for record in records.schema_changes
            if record.properties["uuid"] != older_database.user_change_id
        }
        assert len(records.schema_changes) == 3
        assert sorted(by_status) == ["applied", "failed"]
        applied = by_status["applied"]
        assert {key: applied.properties.get(key) for key in ("source", "version", "created_by", "summary")} == {
            "source": "core_schema_update",
            "version": 2,
            "created_by": SYSTEM_USER_ID,
            "summary": "builtintag_branch_update_and_1_more",
        }
        assert by_status["failed"].properties.get("version") is None
        assert applied.properties["created_at"] == applied.properties["applied_at"]
        assert [edge for edge in applied.edges if edge[0] == SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value] == [
            (SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value, older_database.user_change_id)
        ]
        applied_operation_ids = {
            peer_id
            for edge_type, peer_id in applied.edges
            if edge_type == SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_OPERATION.value
        }
        applied_operations = sorted(
            (record for record in records.operations if record.properties["uuid"] in applied_operation_ids),
            key=lambda record: int(str(record.properties["position"])),
        )
        assert [
            (
                record.properties["operation_type"],
                record.properties["kind"],
                record.properties.get("property_name"),
                record.properties.get("element_name"),
            )
            for record in applied_operations
        ] == [("node_property", TAG_KIND, "branch", None), ("element_add", TAG_KIND, None, ADDED_ATTRIBUTE)]
        assert applied_operations[0].properties["value"] == '"aware"'
        [applied_application_id] = [
            peer_id
            for edge_type, peer_id in applied.edges
            if edge_type == SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_APPLICATION.value
        ]
        [applied_application] = [
            record for record in records.applications if record.properties["uuid"] == applied_application_id
        ]
        assert applied_application.properties["status"] == "applied"
        applied_migrations = [
            record
            for record in records.migrations
            if (SchemaChangeEdgeType.SCHEMA_APPLICATION_HAS_MIGRATION.value, record.properties["uuid"])
            in applied_application.edges
        ]
        assert [
            (
                record.properties["migration_name"],
                record.properties["schema_kind"],
                record.properties["field_name"],
                record.properties["status"],
            )
            for record in applied_migrations
        ] == [("node.attribute.add", TAG_KIND, ADDED_ATTRIBUTE, "applied")], (
            "the branch support of a kind has no migration, so only the added attribute gets one"
        )
        tag = await _stored_tag(db=db, branch=default_branch_scope_class)
        assert (ADDED_ATTRIBUTE in tag.attribute_names, tag.branch) == (True, BranchSupportType.AWARE)

    async def test_step06_up_to_date_core_schema_stores_no_schema_change(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, older_database: OlderDatabase
    ) -> None:
        nbr_records = await count_schema_change_records(db=db)

        status = await check_core_schema_diff(db=db, candidate_builder=build_schema_candidate_builder())
        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        assert status == CoreSchemaStatus.UP_TO_DATE
        assert await count_schema_change_records(db=db) == nbr_records

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import typer

import infrahub.core.migrations.schema.tasks as tasks_module
from infrahub.cli.db import update_core_schema
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
from infrahub.exceptions import ValidationError
from infrahub.lock import GLOBAL_SCHEMA_LOCK
from tests.helpers.schema_change import (
    StoredSchemaChangeRecord,
    build_seeded_operations,
    count_schema_change_records,
    read_branch_schema_change_records,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query import MigrationBaseQuery
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.lock.timeline import LockTimeline

TAG_KIND = "BuiltinTag"
ADDED_ATTRIBUTE = "description"
MIGRATION_FAILURE = "The description of the tags could not be added"
PROCESSING_FAILURE = "HFID of TestDevice refers to peer BuiltinTag with a non-unique combination of attributes"
MIGRATION_CHECKPOINT = "core schema migration"


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


async def _persist_core_schema(db: InfrahubDatabase, branch: Branch, adjust: Callable[[SchemaBranch], None]) -> None:
    schema_branch = registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.load_schema(schema=SchemaRoot(**deprecated_models))
    adjust(schema_branch)
    schema_branch.process()
    await registry.schema.load_schema_to_db(schema=schema_branch, branch=branch, db=db)


def _remove_tag_description(schema_branch: SchemaBranch) -> None:
    tag = schema_branch.get(name=TAG_KIND)
    tag.attributes = [attribute for attribute in tag.attributes if attribute.name != ADDED_ATTRIBUTE]
    schema_branch.set(name=TAG_KIND, schema=tag)


def _make_tag_branch_agnostic(schema_branch: SchemaBranch) -> None:
    tag = schema_branch.get(name=TAG_KIND)
    tag.branch = BranchSupportType.AGNOSTIC
    schema_branch.set(name=TAG_KIND, schema=tag)


def _keep_schema(schema_branch: SchemaBranch) -> None:
    del schema_branch


async def _stored_tag_attribute_names(db: InfrahubDatabase, branch: Branch) -> set[str]:
    stored = await registry.schema.load_schema_from_db(db=db, branch=branch)
    return set(stored.get(name=TAG_KIND, duplicate=False).attribute_names)


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


class OperationBuilderThatFailsProcessing(SchemaOperationBuilder):
    """Raises the error that processing a schema file raises when it refuses the schema."""

    def build(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaOperationBuildResult:
        raise ValidationError(input_value=PROCESSING_FAILURE)


@pytest.fixture
async def older_core_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    """The core schema of a database from an older release, where the tag kind has no description yet."""
    await _persist_core_schema(db=db, branch=default_branch, adjust=_remove_tag_description)


@pytest.fixture
def failing_tag_attribute_add_migration() -> Generator[None]:
    original_map = tasks_module.MIGRATION_MAP.copy()
    tasks_module.MIGRATION_MAP["node.attribute.add"] = TagAttributeAddMigrationThatFails
    yield
    tasks_module.MIGRATION_MAP.clear()
    tasks_module.MIGRATION_MAP.update(original_map)


@pytest.fixture
def checkpointing_tag_attribute_add_migration(recording_lock_timeline: LockTimeline) -> Generator[list[int]]:
    """Record a checkpoint on the lock timeline each time the migration that adds an attribute runs."""
    checkpoints: list[int] = []

    class CheckpointingAttributeAddMigration(NodeAttributeAddMigration):
        async def execute(
            self,
            migration_input: MigrationInput,
            branch: Branch,
            queries: Sequence[type[MigrationBaseQuery]] | None = None,
        ) -> MigrationResult:
            checkpoints.append(recording_lock_timeline.checkpoint(label=MIGRATION_CHECKPOINT))
            return await super().execute(migration_input=migration_input, branch=branch, queries=queries)

    original_map = tasks_module.MIGRATION_MAP.copy()
    tasks_module.MIGRATION_MAP["node.attribute.add"] = CheckpointingAttributeAddMigration
    yield checkpoints
    tasks_module.MIGRATION_MAP.clear()
    tasks_module.MIGRATION_MAP.update(original_map)


class TestCoreSchemaUpdate:
    async def test_core_schema_update_stores_one_applied_schema_change_on_main(
        self, db: InfrahubDatabase, default_branch: Branch, older_core_schema: None
    ) -> None:
        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        records = await _read_main_records(db=db)
        [schema_change] = records.schema_changes
        assert {
            key: schema_change.properties.get(key) for key in ("source", "status", "version", "created_by", "summary")
        } == {
            "source": "core_schema_update",
            "status": "applied",
            "version": 1,
            "created_by": SYSTEM_USER_ID,
            "summary": "builtintag_description_add",
        }
        assert [
            (record.properties["operation_type"], record.properties["kind"], record.properties["element_name"])
            for record in records.operations
        ] == [("element_add", TAG_KIND, ADDED_ATTRIBUTE)]
        assert [record.properties["status"] for record in records.applications] == ["applied"]
        assert [
            (
                record.properties["migration_name"],
                record.properties["schema_kind"],
                record.properties["field_name"],
                record.properties["status"],
            )
            for record in records.migrations
        ] == [("node.attribute.add", TAG_KIND, ADDED_ATTRIBUTE, "applied")]
        assert ADDED_ATTRIBUTE in await _stored_tag_attribute_names(db=db, branch=default_branch)

    async def test_up_to_date_core_schema_stores_no_schema_change(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        await _persist_core_schema(db=db, branch=default_branch, adjust=_keep_schema)

        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        assert await count_schema_change_records(db=db) == 0

    async def test_core_schema_change_follows_the_last_schema_change_of_main(
        self, db: InfrahubDatabase, default_branch: Branch, older_core_schema: None
    ) -> None:
        recorder = build_schema_change_recorder(db=db, default_branch_name=registry.default_branch)
        user_change = await recorder.record_applied(
            branch=default_branch,
            operations=build_seeded_operations(nbr_operations=1),
            at=Timestamp(),
            user_id=SYSTEM_USER_ID,
            source=SchemaChangeSource.USER,
        )

        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        records = await _read_main_records(db=db)
        [core_change] = [
            record for record in records.schema_changes if record.properties["source"] == "core_schema_update"
        ]
        assert core_change.properties["version"] == 2
        assert (
            SchemaChangeEdgeType.SCHEMA_CHANGE_HAS_PARENT.value,
            user_change.schema_change_id,
        ) in core_change.edges

    async def test_unsupported_property_change_is_recorded_without_a_migration(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        await _persist_core_schema(db=db, branch=default_branch, adjust=_make_tag_branch_agnostic)

        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        records = await _read_main_records(db=db)
        [schema_change] = records.schema_changes
        assert (schema_change.properties["status"], schema_change.properties["source"]) == (
            "applied",
            "core_schema_update",
        )
        assert [
            (
                record.properties["operation_type"],
                record.properties["kind"],
                record.properties["property_name"],
                record.properties["value"],
            )
            for record in records.operations
        ] == [("node_property", TAG_KIND, "branch", '"aware"')]
        assert records.migrations == []

    async def test_operations_that_do_not_rebuild_the_core_schema_refuse_the_update(
        self, db: InfrahubDatabase, default_branch: Branch, older_core_schema: None
    ) -> None:
        candidate_builder = SchemaCandidateBuilder(
            operation_builder=SchemaOperationBuilder(), applier=SchemaChangeApplier(), comparer=DifferingKindComparer()
        )

        with pytest.raises(typer.Exit) as exit_info:
            await update_core_schema(db=db, candidate_builder=candidate_builder, initialize=False)

        assert exit_info.value.exit_code == 1
        assert await count_schema_change_records(db=db) == 0
        assert ADDED_ATTRIBUTE not in await _stored_tag_attribute_names(db=db, branch=default_branch)

    async def test_failed_migration_leaves_a_failed_schema_change_and_the_schema_as_before(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        older_core_schema: None,
        failing_tag_attribute_add_migration: None,
    ) -> None:
        with pytest.raises(typer.Exit) as exit_info:
            await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        assert exit_info.value.exit_code == 1
        records = await _read_main_records(db=db)
        [schema_change] = records.schema_changes
        assert {key: schema_change.properties.get(key) for key in ("status", "version", "source")} == {
            "status": "failed",
            "version": None,
            "source": "core_schema_update",
        }
        assert [(record.properties["status"], record.properties["error"]) for record in records.applications] == [
            ("failed", MIGRATION_FAILURE)
        ]
        assert [record.properties["status"] for record in records.migrations] == ["failed"]
        assert ADDED_ATTRIBUTE not in await _stored_tag_attribute_names(db=db, branch=default_branch)

    async def test_update_after_a_failed_one_gets_the_first_version(
        self, db: InfrahubDatabase, default_branch: Branch, older_core_schema: None
    ) -> None:
        original_map = tasks_module.MIGRATION_MAP.copy()
        tasks_module.MIGRATION_MAP["node.attribute.add"] = TagAttributeAddMigrationThatFails
        try:
            with pytest.raises(typer.Exit):
                await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)
        finally:
            tasks_module.MIGRATION_MAP.clear()
            tasks_module.MIGRATION_MAP.update(original_map)

        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        records = await _read_main_records(db=db)
        assert sorted(
            (record.properties["status"], record.properties.get("version")) for record in records.schema_changes
        ) == [("applied", 1), ("failed", None)]

    async def test_core_schema_update_holds_the_global_schema_lock_while_its_migrations_run(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        older_core_schema: None,
        recording_lock_timeline: LockTimeline,
        checkpointing_tag_attribute_add_migration: list[int],
    ) -> None:
        await update_core_schema(db=db, candidate_builder=build_schema_candidate_builder(), initialize=False)

        assert [
            GLOBAL_SCHEMA_LOCK in recording_lock_timeline.held_at(seq=checkpoint)
            for checkpoint in checkpointing_tag_attribute_add_migration
        ] == [True]
        assert [record.properties["status"] for record in (await _read_main_records(db=db)).schema_changes] == [
            "applied"
        ]

    async def test_core_schema_that_processing_refuses_stops_the_update(
        self, db: InfrahubDatabase, default_branch: Branch, older_core_schema: None
    ) -> None:
        candidate_builder = SchemaCandidateBuilder(
            operation_builder=OperationBuilderThatFailsProcessing(),
            applier=SchemaChangeApplier(),
            comparer=SchemaCandidateComparer(),
        )

        with pytest.raises(typer.Exit) as exit_info:
            await update_core_schema(db=db, candidate_builder=candidate_builder, initialize=False)

        assert exit_info.value.exit_code == 1
        assert await count_schema_change_records(db=db) == 0
        assert ADDED_ATTRIBUTE not in await _stored_tag_attribute_names(db=db, branch=default_branch)

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.tasks import (
    KIND_UPDATE_MIGRATION_NAMES,
    SchemaMigrationRequest,
    SchemaMigrationsApplier,
    split_migrations_by_phase,
)
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp

# derived from the class hierarchy rather than reusing the declared name set, so a kind-update
# migration registered without being declared is a failure rather than a matching pair of omissions
VERTEX_DUPLICATING_MIGRATION_NAMES = sorted(
    name
    for name, migration_class in MIGRATION_MAP.items()
    if migration_class is not None and issubclass(migration_class, NodeKindUpdateMigration)
)

LOGGER_NAME = "tests.core.migrations.schema.applier"

NAMESPACE = "Test"
APPLIER_NODE_NAMES = ["Alpha", "Beta", "Gamma"]

ALPHA_KIND = "TestAlpha"
BETA_KIND = "TestBeta"
GAMMA_KIND = "TestGamma"


def _migration_info(migration_name: str) -> SchemaUpdateMigrationInfo:
    return SchemaUpdateMigrationInfo(
        migration_name=migration_name,
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name"),
    )


@dataclass
class SplitMigrationsTestCase:
    name: str
    migration_names: list[str] = field(default_factory=list)
    expected_phase_1_names: list[str] = field(default_factory=list)
    expected_phase_2_names: list[str] = field(default_factory=list)


TEST_CASES = [
    SplitMigrationsTestCase(name="empty"),
    SplitMigrationsTestCase(
        name="only_kind_updates",
        migration_names=["node.inherit_from.update", "node.name.update", "node.namespace.update"],
        expected_phase_1_names=["node.inherit_from.update", "node.name.update", "node.namespace.update"],
    ),
    SplitMigrationsTestCase(
        name="only_other_migrations",
        migration_names=["node.attribute.add", "node.attribute.remove", "attribute.kind.update"],
        expected_phase_2_names=["node.attribute.add", "node.attribute.remove", "attribute.kind.update"],
    ),
    SplitMigrationsTestCase(
        name="mixed_preserves_relative_order",
        migration_names=[
            "node.attribute.add",
            "node.inherit_from.update",
            "attribute.kind.update",
            "node.name.update",
            "node.attribute.remove",
            "node.namespace.update",
        ],
        expected_phase_1_names=["node.inherit_from.update", "node.name.update", "node.namespace.update"],
        expected_phase_2_names=["node.attribute.add", "attribute.kind.update", "node.attribute.remove"],
    ),
    SplitMigrationsTestCase(
        name="duplicates_kept",
        migration_names=["node.inherit_from.update", "node.attribute.add", "node.inherit_from.update"],
        expected_phase_1_names=["node.inherit_from.update", "node.inherit_from.update"],
        expected_phase_2_names=["node.attribute.add"],
    ),
]


@pytest.mark.parametrize("test_case", TEST_CASES, ids=[test_case.name for test_case in TEST_CASES])
def test_split_migrations_by_phase(test_case: SplitMigrationsTestCase) -> None:
    migrations = [_migration_info(migration_name=name) for name in test_case.migration_names]

    phase_1, phase_2 = split_migrations_by_phase(migrations=migrations)

    assert [migration.migration_name for migration in phase_1] == test_case.expected_phase_1_names
    assert [migration.migration_name for migration in phase_2] == test_case.expected_phase_2_names


def test_split_covers_every_kind_update_backed_migration() -> None:
    """Every migration whose class duplicates vertices must land in phase one, declared or not."""
    migrations = [_migration_info(migration_name=name) for name in sorted(MIGRATION_MAP)]

    phase_1, phase_2 = split_migrations_by_phase(migrations=migrations)

    assert [migration.migration_name for migration in phase_1] == VERTEX_DUPLICATING_MIGRATION_NAMES
    assert sorted(migration.migration_name for migration in phase_2) == sorted(
        set(MIGRATION_MAP) - set(VERTEX_DUPLICATING_MIGRATION_NAMES)
    )


def test_declared_kind_update_names_match_the_vertex_duplicating_migrations() -> None:
    assert sorted(KIND_UPDATE_MIGRATION_NAMES) == VERTEX_DUPLICATING_MIGRATION_NAMES


@dataclass
class ExecutorCall:
    labels: list[str]
    max_concurrent_execution: int | None


class RecordingMigrationExecutor:
    """Records each group of migrations it is handed and the concurrency cap it was asked for.

    Running the group is the executor's job, so a group arrives as one call and the cap can only be
    checked as a request, not as observed serialization. The yields between the enter and exit events
    keep the ordering observable: an applier that started both groups at once would interleave them.
    """

    def __init__(self, errors_by_label: dict[str, list[str]] | None = None, yields: int = 5) -> None:
        self.errors_by_label = errors_by_label or {}
        self.yields = yields
        self.calls: list[ExecutorCall] = []
        self.events: list[str] = []

    async def execute(
        self,
        requests: Sequence[SchemaMigrationRequest],
        max_concurrent_execution: int | None = None,
    ) -> list[SchemaMigrationPathResponseData]:
        labels = [
            _label(migration_name=request.migration_name, schema_kind=request.schema_path.schema_kind)
            for request in requests
        ]
        self.calls.append(ExecutorCall(labels=labels, max_concurrent_execution=max_concurrent_execution))

        self.events.append(f"enter:{','.join(labels)}")
        for _ in range(self.yields):
            await asyncio.sleep(0)
        self.events.append(f"exit:{','.join(labels)}")

        return [
            SchemaMigrationPathResponseData(
                migration_name=request.migration_name,
                schema_path=request.schema_path,
                errors=self.errors_by_label.get(label, []),
                nbr_migrations_executed=1,
            )
            for label, request in zip(labels, requests, strict=True)
        ]


def _label(migration_name: str, schema_kind: str) -> str:
    return f"{migration_name}@{schema_kind}"


def _labels(work: list[tuple[str, str]]) -> list[str]:
    return [_label(migration_name=migration_name, schema_kind=schema_kind) for migration_name, schema_kind in work]


def _build_schema() -> SchemaBranch:
    # built per call because load_schema takes ownership of the nodes it is handed
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            version="1.0",
            nodes=[
                NodeSchema(
                    name=node_name,
                    namespace=NAMESPACE,
                    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                )
                for node_name in APPLIER_NODE_NAMES
            ],
        )
    )
    schema.process()
    return schema


def _apply_message(migrations: list[tuple[str, str]]) -> SchemaApplyMigrationData:
    schema = _build_schema()
    return SchemaApplyMigrationData(
        branch=Branch(name="main"),
        new_schema=schema,
        previous_schema=schema,
        at=Timestamp(),
        migrations=[
            SchemaUpdateMigrationInfo(
                migration_name=migration_name,
                path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=schema_kind),
            )
            for migration_name, schema_kind in migrations
        ],
    )


def _build_applier(executor: RecordingMigrationExecutor) -> SchemaMigrationsApplier:
    return SchemaMigrationsApplier(executor=executor, log=logging.getLogger(LOGGER_NAME))


KIND_UPDATE_WORK = [
    ("node.inherit_from.update", ALPHA_KIND),
    ("node.name.update", BETA_KIND),
    ("node.namespace.update", GAMMA_KIND),
]
OTHER_WORK = [
    ("node.attribute.add", ALPHA_KIND),
    ("attribute.kind.update", BETA_KIND),
    ("node.attribute.remove", GAMMA_KIND),
]


async def test_apply_no_migrations_runs_nothing() -> None:
    executor = RecordingMigrationExecutor()

    errors = await _build_applier(executor=executor).apply(message=_apply_message(migrations=[]))

    assert errors == []
    assert executor.calls == []


async def test_kind_updates_are_dispatched_first_and_capped_to_one_at_a_time() -> None:
    """Two concurrent vertex duplications can each create a replacement vertex, so the cap must be 1."""
    executor = RecordingMigrationExecutor()
    # interleave the two phases in the input so the grouping cannot come from the submission order
    migrations = [work for pair in zip(OTHER_WORK, KIND_UPDATE_WORK, strict=True) for work in pair]

    errors = await _build_applier(executor=executor).apply(message=_apply_message(migrations=migrations))

    assert errors == []
    assert executor.calls == [
        ExecutorCall(labels=_labels(KIND_UPDATE_WORK), max_concurrent_execution=1),
        ExecutorCall(labels=_labels(OTHER_WORK), max_concurrent_execution=None),
    ]


async def test_an_empty_phase_is_not_dispatched() -> None:
    executor = RecordingMigrationExecutor()

    errors = await _build_applier(executor=executor).apply(message=_apply_message(migrations=OTHER_WORK))

    assert errors == []
    assert executor.calls == [ExecutorCall(labels=_labels(OTHER_WORK), max_concurrent_execution=None)]


async def test_every_kind_update_finishes_before_any_other_migration_starts() -> None:
    executor = RecordingMigrationExecutor()
    migrations = [work for pair in zip(OTHER_WORK, KIND_UPDATE_WORK, strict=True) for work in pair]

    errors = await _build_applier(executor=executor).apply(message=_apply_message(migrations=migrations))

    assert errors == []
    kind_update_group = ",".join(_labels(KIND_UPDATE_WORK))
    other_group = ",".join(_labels(OTHER_WORK))
    assert executor.events == [
        f"enter:{kind_update_group}",
        f"exit:{kind_update_group}",
        f"enter:{other_group}",
        f"exit:{other_group}",
    ]


async def test_kind_update_errors_skip_the_remaining_migrations(caplog: pytest.LogCaptureFixture) -> None:
    failing_label = _label(migration_name="node.name.update", schema_kind=BETA_KIND)
    executor = RecordingMigrationExecutor(errors_by_label={failing_label: ["duplication failed"]})
    migrations = KIND_UPDATE_WORK + OTHER_WORK

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        errors = await _build_applier(executor=executor).apply(message=_apply_message(migrations=migrations))

    assert errors == ["duplication failed"]
    assert "Kind-update migrations reported errors, skipping the remaining migrations" in caplog.text
    assert executor.calls == [ExecutorCall(labels=_labels(KIND_UPDATE_WORK), max_concurrent_execution=1)]

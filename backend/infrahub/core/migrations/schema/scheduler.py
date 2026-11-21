from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.migrations.schema.phases import MigrationPhase

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.migrations.shared import SchemaMigration
    from infrahub.core.models import SchemaUpdateMigrationInfo
    from infrahub.core.schema.schema_branch import SchemaBranch

_PHASE_RANKS: dict[MigrationPhase, int] = {phase: rank for rank, phase in enumerate(MigrationPhase)}


@dataclass(frozen=True)
class PositionedMigration:
    position: int
    """The index of the migration in the migrations sorted by phase, then by schema path, then by migration name."""
    migration: SchemaUpdateMigrationInfo


@dataclass(frozen=True)
class ScheduledPhase:
    phase: MigrationPhase
    groups: tuple[tuple[PositionedMigration, ...], ...]
    """Groups run at the same time, and the migrations of a group run one after another."""


@dataclass(frozen=True)
class MigrationSchedule:
    migrations: tuple[PositionedMigration, ...]
    phases: tuple[ScheduledPhase, ...]


@dataclass(frozen=True)
class _ClassifiedMigration:
    migration: SchemaUpdateMigrationInfo
    migration_class: type[SchemaMigration]

    @property
    def sort_key(self) -> tuple[int, str, str, str, str, str]:
        path = self.migration.path
        return (
            _PHASE_RANKS[self.migration_class.phase],
            path.schema_kind,
            path.field_name or "",
            path.property_name or "",
            path.path_type.value,
            self.migration.migration_name,
        )


class MigrationScheduler:
    """Decide the order in which the migrations of one schema application run."""

    def __init__(self, migration_classes: Mapping[str, type[SchemaMigration] | None]) -> None:
        self.migration_classes = migration_classes

    def schedule(
        self,
        migrations: Sequence[SchemaUpdateMigrationInfo],
        previous_schema: SchemaBranch,
        new_schema: SchemaBranch,
    ) -> MigrationSchedule:
        """Give each migration a position in phase order, and split each phase into groups.

        The migrations come in the order of a set, so the sort keeps the positions the same between two runs of a load.

        Raises:
            ValueError: When a migration name has no migration class.

        """
        classified = sorted((self._classify(migration=migration) for migration in migrations), key=lambda c: c.sort_key)
        positioned = tuple(
            PositionedMigration(position=position, migration=item.migration) for position, item in enumerate(classified)
        )

        phases: list[ScheduledPhase] = []
        for phase in MigrationPhase:
            members = [
                (item, positioned_migration)
                for item, positioned_migration in zip(classified, positioned, strict=True)
                if item.migration_class.phase == phase
            ]
            if not members:
                continue
            if phase == MigrationPhase.KIND_UPDATE:
                # concurrent duplications of overlapping vertices can each create a replacement vertex
                groups = (tuple(positioned_migration for _, positioned_migration in members),)
            else:
                groups = self._group(members=members, previous_schema=previous_schema, new_schema=new_schema)
            phases.append(ScheduledPhase(phase=phase, groups=groups))

        return MigrationSchedule(migrations=positioned, phases=tuple(phases))

    def _classify(self, migration: SchemaUpdateMigrationInfo) -> _ClassifiedMigration:
        migration_class = self.migration_classes.get(migration.migration_name)
        if migration_class is None:
            raise ValueError(f"No migration class for {migration.migration_name!r} on {migration.path.get_path()!r}")
        return _ClassifiedMigration(migration=migration, migration_class=migration_class)

    @staticmethod
    def _group(
        members: Sequence[tuple[_ClassifiedMigration, PositionedMigration]],
        previous_schema: SchemaBranch,
        new_schema: SchemaBranch,
    ) -> tuple[tuple[PositionedMigration, ...], ...]:
        """Put migrations whose changed kinds overlap, directly or through other migrations, in one group."""
        groups: list[tuple[set[str], list[PositionedMigration]]] = []
        for item, positioned_migration in members:
            changed_kinds = set(
                item.migration_class.get_changed_kinds(
                    schema_path=item.migration.path, previous_schema=previous_schema, new_schema=new_schema
                )
            )
            overlapping = [group for group in groups if group[0] & changed_kinds]
            merged_kinds = changed_kinds.union(*(kinds for kinds, _ in overlapping))
            merged_members = sorted(
                [positioned_migration, *(member for _, group_members in overlapping for member in group_members)],
                key=lambda member: member.position,
            )
            groups = [group for group in groups if not group[0] & changed_kinds]
            groups.append((merged_kinds, merged_members))

        ordered = sorted(groups, key=lambda group: group[1][0].position)
        return tuple(tuple(group_members) for _, group_members in ordered)

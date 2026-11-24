from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from infrahub.core.schema_change.migration_recorder import MigrationRecorder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
    from infrahub.core.models import SchemaUpdateMigrationInfo

REGISTER = "register"
MIGRATION_STARTED = "migration_started"
MIGRATION_ENDED = "migration_ended"


@dataclass(frozen=True)
class MigrationRecorderCall:
    method: str
    arguments: dict[str, object]


class RecordingMigrationRecorder(MigrationRecorder):
    def __init__(self) -> None:
        self.calls: list[MigrationRecorderCall] = []

    @override
    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None:
        self.calls.append(MigrationRecorderCall(method=REGISTER, arguments={"migrations": list(migrations)}))

    @override
    async def migration_started(self, *, position: int) -> None:
        self.calls.append(MigrationRecorderCall(method=MIGRATION_STARTED, arguments={"position": position}))

    @override
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None:
        self.calls.append(
            MigrationRecorderCall(method=MIGRATION_ENDED, arguments={"position": position, "result": result})
        )


class FailingMigrationRecorder(RecordingMigrationRecorder):
    """Raise when the end of a migration at one of the given positions is recorded, as a record write that loses its connection does."""

    def __init__(self, failing_positions: set[int]) -> None:
        super().__init__()
        self.failing_positions = failing_positions

    @override
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None:
        await super().migration_ended(position=position, result=result)
        if position in self.failing_positions:
            raise RuntimeError(f"record write failed: {position}")

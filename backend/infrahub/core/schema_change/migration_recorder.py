from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
    from infrahub.core.models import SchemaUpdateMigrationInfo


class MigrationRecorder(ABC):
    """Receive the progress of the migrations of one schema application.

    `position` is the index of a migration in the list given to `register`, because two migrations
    can have the same name and the same schema path. No method raises when a record cannot be written.
    """

    @abstractmethod
    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None: ...

    @abstractmethod
    async def batch_started(self, *, positions: Sequence[int]) -> None: ...

    @abstractmethod
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None: ...


class NoRecordMigrationRecorder(MigrationRecorder):
    """Record nothing, for migrations that run without a schema application."""

    @override
    async def register(self, *, migrations: Sequence[SchemaUpdateMigrationInfo]) -> None:
        return

    @override
    async def batch_started(self, *, positions: Sequence[int]) -> None:
        return

    @override
    async def migration_ended(self, *, position: int, result: SchemaMigrationPathResponseData) -> None:
        return

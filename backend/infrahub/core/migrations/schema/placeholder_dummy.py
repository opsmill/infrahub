from __future__ import annotations

from typing import Sequence

from ..shared import MigrationQuery, SchemaMigration


class PlaceholderDummyMigration(SchemaMigration):
    name: str = "dummy.placeholder"
    queries: Sequence[type[MigrationQuery]] = []  # type: ignore[assignment]

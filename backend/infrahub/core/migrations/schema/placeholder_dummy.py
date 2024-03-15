from __future__ import annotations

from typing import Sequence

from pydantic import Field

from ..shared import MigrationQuery, SchemaMigration


class PlaceholderDummyMigration(SchemaMigration):
    name: str = "dummy.placeholder"
    queries: Sequence[type[MigrationQuery]] = Field(default_factory=list)

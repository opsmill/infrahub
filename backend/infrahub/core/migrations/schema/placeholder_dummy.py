from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from pydantic import Field

from ..shared import SchemaMigration

if TYPE_CHECKING:
    from ..query import MigrationBaseQuery


class PlaceholderDummyMigration(SchemaMigration):
    name: str = "dummy.placeholder"
    queries: Sequence[type[MigrationBaseQuery]] = Field(default_factory=list)

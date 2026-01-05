from __future__ import annotations

from typing import Sequence

from pydantic import Field

from ..query import MigrationBaseQuery  # noqa: TC001
from ..shared import SchemaMigration


class PlaceholderDummyMigration(SchemaMigration):
    name: str = "dummy.placeholder"
    queries: Sequence[type[MigrationBaseQuery]] = Field(default_factory=list)

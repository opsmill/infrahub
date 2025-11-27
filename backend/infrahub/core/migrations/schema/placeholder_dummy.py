from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from ..query import MigrationBaseQuery  # noqa: TC001
from ..shared import SchemaMigration

if TYPE_CHECKING:
    from collections.abc import Sequence


class PlaceholderDummyMigration(SchemaMigration):
    name: str = "dummy.placeholder"
    queries: Sequence[type[MigrationBaseQuery]] = Field(default_factory=list)

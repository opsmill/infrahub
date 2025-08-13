from __future__ import annotations

from typing import Any, Sequence

from ..query import AttributeMigrationQuery
from ..query.attribute_rename import AttributeInfo, AttributeRenameQuery
from ..shared import AttributeSchemaMigration


class AttributeKindUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.kind.update"
    queries: Sequence[type[AttributeMigrationQuery]] = []  # type: ignore[assignment]

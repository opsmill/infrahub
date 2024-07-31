from __future__ import annotations

from typing import Sequence

from ..query import NodeDuplicateMigrationQuery
from ..shared import MigrationQuery, SchemaMigration


class NodeKindUpdateMigrationQuery01(NodeDuplicateMigrationQuery):
    name = "migration_node_kind_update_01"


class NodeKindUpdateMigration(SchemaMigration):
    name: str = "node.kind.update"
    queries: Sequence[type[MigrationQuery]] = [NodeKindUpdateMigrationQuery01]  # type: ignore[assignment]

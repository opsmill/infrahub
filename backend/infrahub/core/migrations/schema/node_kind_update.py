from __future__ import annotations

from typing import Any, Sequence

from ..query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from ..shared import MigrationQuery, SchemaMigration


class NodeKindUpdateMigrationQuery01(MigrationQuery, NodeDuplicateQuery):
    name = "migration_node_kind_update_01"

    def __init__(
        self,
        migration: SchemaMigration,
        **kwargs: Any,
    ):
        new_node = SchemaNodeInfo(
            name=migration.new_schema.name,
            namespace=migration.new_schema.namespace,
            branch_support=migration.new_schema.branch.value,
            labels=migration.new_schema.get_labels(),
            kind=migration.new_schema.kind,
        )
        previous_node = SchemaNodeInfo(
            name=migration.previous_schema.name,
            namespace=migration.previous_schema.namespace,
            branch_support=migration.previous_schema.branch.value,
            labels=migration.previous_schema.get_labels(),
            kind=migration.previous_schema.kind,
        )
        super().__init__(migration=migration, new_node=new_node, previous_node=previous_node, **kwargs)

    def get_nbr_migrations_executed(self) -> int:
        return self.stats.get_counter(name="nodes_created")


class NodeKindUpdateMigration(SchemaMigration):
    name: str = "node.kind.update"
    queries: Sequence[type[MigrationQuery]] = [NodeKindUpdateMigrationQuery01]  # type: ignore[assignment]

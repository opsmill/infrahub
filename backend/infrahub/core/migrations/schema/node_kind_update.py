from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from ..query import MigrationQuery
from ..query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from ..shared import SchemaMigration

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


def _schema_node_info(schema: MainSchemaTypes) -> SchemaNodeInfo:
    return SchemaNodeInfo(
        name=schema.name,
        namespace=schema.namespace,
        branch_support=schema.branch.value,
        labels=schema.get_labels(),
        kind=schema.kind,
    )


class NodeKindUpdateMigrationQuery01(MigrationQuery, NodeDuplicateQuery):
    name = "migration_node_kind_update_01"

    def __init__(
        self,
        migration: SchemaMigration,
        **kwargs: Any,
    ) -> None:
        super().__init__(migration=migration, kind_updates_map=self._build_kind_updates(migration=migration), **kwargs)

    def _build_kind_updates(self, migration: SchemaMigration) -> dict[str, SchemaNodeInfo]:
        kind_updates = {migration.previous_schema.kind: _schema_node_info(schema=migration.new_schema)}

        # The generated Profile/Template kinds never appear in the schema diff, so their vertices
        # are only relabelled as extra populations of the source kind's own migration
        for derived in migration.derived_schemas:
            if derived.previous.kind == derived.new.kind and derived.previous.get_labels() == derived.new.get_labels():
                continue
            kind_updates[derived.previous.kind] = _schema_node_info(schema=derived.new)

        return kind_updates

    def get_nbr_migrations_executed(self) -> int:
        return self.stats.get_counter(name="nodes_created")


class NodeKindUpdateMigration(SchemaMigration):
    name: str = "node.kind.update"
    queries: Sequence[type[MigrationQuery]] = [NodeKindUpdateMigrationQuery01]  # type: ignore[assignment]

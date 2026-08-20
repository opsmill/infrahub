from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import SchemaPathType
from infrahub.core.path import SchemaPath

from ..query import MigrationQuery
from ..query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from ..shared import MigrationInput, MigrationResult, SchemaMigration
from .node_attribute_add import NodeAttributeAddMigration

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.attribute_schema import AttributeSchema

    from ..query import MigrationBaseQuery


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

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        result = await super().execute(migration_input=migration_input, branch=branch, queries=queries)
        if result.errors:
            return result

        # explicitly run migrations to add the new attributes to existing instances
        for attribute in self._newly_inherited_attributes():
            sub_migration = NodeAttributeAddMigration(
                new_node_schema=self.new_node_schema,
                previous_node_schema=self.previous_node_schema,
                schema_path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind=self.new_schema.kind,
                    field_name=attribute.name,
                ),
                force_inherited=True,
            )
            sub_result = await sub_migration.execute(migration_input=migration_input, branch=branch)
            result.errors.extend(sub_result.errors)
            result.nbr_migrations_executed += sub_result.nbr_migrations_executed
            if result.errors:
                break

        return result

    def _newly_inherited_attributes(self) -> list[AttributeSchema]:
        new_names = set(self.new_schema.attribute_names) - set(self.previous_schema.attribute_names)
        attributes = (self.new_schema.get_attribute(name=name) for name in sorted(new_names))
        return [attribute for attribute in attributes if attribute.inherited]

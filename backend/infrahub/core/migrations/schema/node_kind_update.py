from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.constants import MigrationIdentifier, SchemaPathType
from infrahub.core.path import SchemaPath

from ..query import MigrationQuery
from ..query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from ..shared import MigrationInput, MigrationResult, SchemaMigration
from .node_attribute_add import NodeAttributeAddMigration

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.attribute_schema import AttributeSchema

    from ..query import MigrationBaseQuery


class NodeKindUpdateMigrationQuery01(MigrationQuery, NodeDuplicateQuery):
    name = "migration_node_kind_update_01"

    def __init__(
        self,
        migration: SchemaMigration,
        **kwargs: Any,
    ) -> None:
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
    """Duplicates a kind's node vertices under a new label set.

    Usable on its own to relabel a kind. The registered migrations below subclass it, so this name
    is a placeholder they each replace — it is deliberately not one of the registered identifiers.
    """

    name: str = "node.kind.update"
    queries: Sequence[type[MigrationQuery]] = [NodeKindUpdateMigrationQuery01]  # type: ignore[assignment]


class NodeNameUpdateMigration(NodeKindUpdateMigration):
    name: str = MigrationIdentifier.NODE_NAME_UPDATE.value


class NodeNamespaceUpdateMigration(NodeKindUpdateMigration):
    name: str = MigrationIdentifier.NODE_NAMESPACE_UPDATE.value


class NodeInheritFromUpdateMigration(NodeKindUpdateMigration):
    """Relabels the vertices and creates the attributes the kind gained from its new generics.

    A rename relabels vertices too but brings in no attributes, so only this migration creates the
    rows that pre-existing instances would otherwise be missing.
    """

    name: str = MigrationIdentifier.NODE_INHERIT_FROM_UPDATE.value

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

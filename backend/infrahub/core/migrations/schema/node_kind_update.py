from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core import registry
from infrahub.core.constants import infrahubkind

from ..query import MigrationQuery
from ..query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from ..shared import MigrationInput, MigrationResult, SchemaMigration

if TYPE_CHECKING:
    from infrahub.core.branch import Branch


# Pool kinds and their text attributes that store node kind references
POOL_NODE_KIND_ATTRIBUTES: list[tuple[str, str]] = [
    (infrahubkind.NUMBERPOOL, "node"),
    (infrahubkind.IPADDRESSPOOL, "default_address_type"),
    (infrahubkind.IPPREFIXPOOL, "default_prefix_type"),
]


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
    name: str = "node.kind.update"
    queries: Sequence[type[MigrationQuery]] = [NodeKindUpdateMigrationQuery01]  # type: ignore[assignment]

    async def execute_post_queries(
        self,
        migration_input: MigrationInput,
        result: MigrationResult,
        branch: Branch,
    ) -> MigrationResult:
        """Update pool nodes that reference the renamed node kind."""
        old_kind = self.previous_schema.kind
        new_kind = self.new_schema.kind

        # Skip if kind hasn't actually changed (e.g., only inherit_from changed)
        if old_kind == new_kind:
            return result

        db = migration_input.db

        for pool_kind, attr_name in POOL_NODE_KIND_ATTRIBUTES:
            # Skip if the pool schema isn't registered (e.g., in test environments)
            if not registry.schema.has(name=pool_kind, branch=branch.name):
                continue

            # Query for pool nodes where the attribute value matches the old kind
            pools = await registry.manager.query(
                db=db,
                branch=branch,
                schema=pool_kind,
                filters={attr_name: {"value": old_kind}},
            )

            for pool in pools:
                attr = pool.get_attribute(name=attr_name)
                attr.value = new_kind
                await pool.save(db=db, fields=[attr_name], at=migration_input.at)
                result.nbr_migrations_executed += 1

        return result

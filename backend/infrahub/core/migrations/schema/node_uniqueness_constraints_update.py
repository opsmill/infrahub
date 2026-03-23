from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from infrahub.core.constants import SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema

from ..query import MigrationBaseQuery  # noqa: TC001
from ..shared import AttributeSchemaMigration, MigrationInput, MigrationResult, SchemaMigration
from .attribute_supports_generated_schema import (
    ProfilesAttributeAddMigrationQuery,
    ProfilesAttributeRemoveMigrationQuery,
)

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch


class NodeUniquenessConstraintsUpdateMigration(SchemaMigration):
    name: str = "node.uniqueness_constraints.update"
    queries: Sequence[type[MigrationBaseQuery]] = []

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,  # noqa: ARG002
    ) -> MigrationResult:
        result = MigrationResult()

        if not isinstance(self.new_schema, (NodeSchema, GenericSchema)):
            return result
        if not self.new_schema.generate_profile:
            return result

        for attr in self.new_schema.attributes:
            if not attr.support_profiles or not attr.optional:
                continue

            previous_in_constraint = self.previous_schema.check_attr_in_uniqueness_constraint(attr=attr.name)
            new_in_constraint = self.new_schema.check_attr_in_uniqueness_constraint(attr=attr.name)

            if previous_in_constraint == new_in_constraint:
                continue

            attr_migration = AttributeSchemaMigration(
                name=f"node.uniqueness_constraints.update.{attr.name}",
                queries=[],
                new_node_schema=self.new_node_schema,
                previous_node_schema=self.previous_node_schema,
                schema_path=SchemaPath(
                    path_type=SchemaPathType.ATTRIBUTE,
                    schema_kind=self.new_schema.kind,
                    field_name=attr.name,
                ),
            )

            query_class = (
                ProfilesAttributeRemoveMigrationQuery if new_in_constraint else ProfilesAttributeAddMigrationQuery
            )
            attr_result = await attr_migration.execute(
                migration_input=migration_input, branch=branch, queries=[query_class]
            )
            result.errors.extend(attr_result.errors)
            result.nbr_migrations_executed += attr_result.nbr_migrations_executed
            if result.errors:
                break

        return result

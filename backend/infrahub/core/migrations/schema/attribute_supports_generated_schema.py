from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.query.attribute_remove import AttributeRemoveQuery
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema

from ..query import AttributeMigrationQuery, MigrationBaseQuery
from ..query.attribute_add import AttributeAddQuery
from ..shared import AttributeSchemaMigration, MigrationInput, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.core.schema import MainSchemaTypes


def _get_profile_node_kinds(schema: MainSchemaTypes) -> list[str]:
    if not isinstance(schema, (NodeSchema, GenericSchema)):
        return [schema.kind]
    schema_kinds = [f"Profile{schema.kind}"]
    if isinstance(schema, GenericSchema) and schema.used_by:
        schema_kinds += [f"Profile{kind}" for kind in schema.used_by]
    return schema_kinds


def _get_template_node_kinds(schema: MainSchemaTypes) -> list[str]:
    if not isinstance(schema, (NodeSchema, GenericSchema)):
        return [schema.kind]
    schema_kinds = [f"Template{schema.kind}"]
    if isinstance(schema, GenericSchema) and schema.used_by:
        schema_kinds += [f"Template{kind}" for kind in schema.used_by]
    return schema_kinds


class ProfilesAttributeAddMigrationQuery(AttributeMigrationQuery, AttributeAddQuery):
    name = "migration_profiles_attribute_add"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        node_kinds = _get_profile_node_kinds(migration.new_schema)
        super().__init__(
            migration=migration,
            node_kinds=node_kinds,
            attribute_name=migration.new_attribute_schema.name,
            attribute_kind=migration.new_attribute_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch().value,
            default_value=migration.new_attribute_schema.default_value,
            **kwargs,
        )


class ProfilesAttributeRemoveMigrationQuery(AttributeMigrationQuery, AttributeRemoveQuery):
    name = "migration_profiles_attribute_remove"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        node_kinds = _get_profile_node_kinds(migration.new_schema)
        super().__init__(
            migration=migration,
            attribute_name=migration.new_attribute_schema.name,
            node_kinds=node_kinds,
            **kwargs,
        )


class TemplatesAttributeAddMigrationQuery(AttributeMigrationQuery, AttributeAddQuery):
    name = "migration_templates_attribute_add"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        node_kinds = _get_template_node_kinds(migration.new_schema)
        super().__init__(
            migration=migration,
            node_kinds=node_kinds,
            attribute_name=migration.new_attribute_schema.name,
            attribute_kind=migration.new_attribute_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch().value,
            default_value=migration.new_attribute_schema.default_value,
            **kwargs,
        )


class TemplatesAttributeRemoveMigrationQuery(AttributeMigrationQuery, AttributeRemoveQuery):
    name = "migration_templates_attribute_remove"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        node_kinds = _get_template_node_kinds(migration.new_schema)
        super().__init__(
            migration=migration,
            attribute_name=migration.new_attribute_schema.name,
            node_kinds=node_kinds,
            **kwargs,
        )


class AttributeSupportsGeneratedSchemaMigration(AttributeSchemaMigration):
    name: str = "attribute.supports_generated_schema.update"
    queries: Sequence[type[MigrationBaseQuery]] = []

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,  # noqa: ARG002
    ) -> MigrationResult:
        # the attribute is new, so there cannot be existing profiles/templates to update
        if self.previous_attribute_schema.id is None:
            return MigrationResult()

        all_queries: list[type[AttributeMigrationQuery]] = []

        # Check profile support changes
        if (
            isinstance(self.new_schema, (NodeSchema, GenericSchema))
            and self.new_schema.generate_profile
            and self.previous_attribute_schema.support_profiles != self.new_attribute_schema.support_profiles
        ):
            if self.new_attribute_schema.support_profiles:
                all_queries.append(ProfilesAttributeAddMigrationQuery)
            else:
                all_queries.append(ProfilesAttributeRemoveMigrationQuery)

        # Check template support changes
        if (
            isinstance(self.new_schema, NodeSchema)
            and self.new_schema.generate_template
            and self.previous_attribute_schema.support_templates != self.new_attribute_schema.support_templates
        ):
            if self.new_attribute_schema.support_templates:
                all_queries.append(TemplatesAttributeAddMigrationQuery)
            else:
                all_queries.append(TemplatesAttributeRemoveMigrationQuery)

        if not all_queries:
            return MigrationResult()

        return await super().execute(migration_input=migration_input, branch=branch, queries=all_queries)

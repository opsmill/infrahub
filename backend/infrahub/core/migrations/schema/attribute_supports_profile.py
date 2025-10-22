from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.migrations.query.attribute_remove import AttributeRemoveQuery
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema

from ..query import AttributeMigrationQuery, MigrationBaseQuery
from ..query.attribute_add import AttributeAddQuery
from ..shared import AttributeSchemaMigration, MigrationResult

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


def _get_node_kinds(schema: MainSchemaTypes) -> list[str]:
    if not isinstance(schema, (NodeSchema, GenericSchema)):
        return [schema.kind]
    schema_kinds = [f"Profile{schema.kind}"]
    if isinstance(schema, GenericSchema) and schema.used_by:
        schema_kinds += [f"Profile{kind}" for kind in schema.used_by]
    return schema_kinds


class ProfilesAttributeAddMigrationQuery(AttributeMigrationQuery, AttributeAddQuery):
    name = "migration_profiles_attribute_add"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ):
        node_kinds = _get_node_kinds(migration.new_schema)
        super().__init__(
            migration=migration,
            node_kinds=node_kinds,
            attribute_name=migration.new_attribute_schema.name,
            attribute_kind=migration.new_attribute_schema.kind,
            branch_support=migration.new_attribute_schema.get_branch(),
            default_value=migration.new_attribute_schema.default_value,
            **kwargs,
        )


class ProfilesAttributeRemoveMigrationQuery(AttributeMigrationQuery, AttributeRemoveQuery):
    name = "migration_profiles_attribute_remove"

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ):
        node_kinds = _get_node_kinds(migration.new_schema)
        super().__init__(
            migration=migration,
            attribute_name=migration.new_attribute_schema.name,
            node_kinds=node_kinds,
            **kwargs,
        )


class AttributeSupportsProfileUpdateMigration(AttributeSchemaMigration):
    name: str = "attribute.supports_profile.update"
    queries: Sequence[type[MigrationBaseQuery]] = []

    async def execute(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        at: Timestamp | str | None = None,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,  # noqa: ARG002
    ) -> MigrationResult:
        if (
            # no change in whether the attribute should be used on profiles
            self.previous_attribute_schema.support_profiles == self.new_attribute_schema.support_profiles
            # the attribute is new, so there cannot be existing profiles to update
            or self.previous_attribute_schema.id is None
        ):
            return MigrationResult()
        profiles_queries: list[type[AttributeMigrationQuery]] = []
        if self.new_attribute_schema.support_profiles:
            profiles_queries.append(ProfilesAttributeAddMigrationQuery)
        if not self.new_attribute_schema.support_profiles:
            profiles_queries.append(ProfilesAttributeRemoveMigrationQuery)

        return await super().execute(db=db, branch=branch, at=at, queries=profiles_queries)

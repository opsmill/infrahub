from __future__ import annotations

from collections.abc import Sequence  # noqa: TC003  needed for pydantic
from typing import TYPE_CHECKING, Any

from ..query import AttributeMigrationQuery
from ..query.attribute_remove import AttributeRemoveQuery
from ..query.owner_set_attribute import OwnerSetKeyMigrationQuery, profile_and_template_kinds
from ..shared import AttributeSchemaMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class NodeAttributeRemoveMigrationQuery01(AttributeMigrationQuery, AttributeRemoveQuery):
    name = "migration_node_attribute_remove_01"
    insert_return: bool = False

    def __init__(
        self,
        migration: AttributeSchemaMigration,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            migration=migration,
            attribute_name=migration.previous_attribute_schema.name,
            node_kinds=[migration.new_schema.kind],
            **kwargs,
        )


class NodeAttributeRemoveMigrationQuery02(AttributeMigrationQuery, OwnerSetKeyMigrationQuery):
    """Close the owners that profiles and object templates give to the attribute."""

    name = "migration_node_attribute_remove_02"

    def __init__(self, migration: AttributeSchemaMigration, **kwargs: Any) -> None:
        super().__init__(
            migration=migration,
            node_kinds=[],
            set_key={"attribute": migration.previous_attribute_schema.name},
            **kwargs,
        )

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.node_kinds = profile_and_template_kinds(
            db=db,
            branch=self.branch,
            node_kind=self.migration.new_schema.kind,
            attribute_name=self.set_key["attribute"],
        )
        await super().query_init(db=db, **kwargs)


class NodeAttributeRemoveMigration(AttributeSchemaMigration):
    name: str = "node.attribute.remove"
    queries: Sequence[type[AttributeMigrationQuery]] = [  # type: ignore[assignment]
        NodeAttributeRemoveMigrationQuery01,
        NodeAttributeRemoveMigrationQuery02,
    ]

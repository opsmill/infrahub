from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import (
    OBJECT_TEMPLATE_NAME_ATTR,
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    RelationshipCardinality,
    RelationshipKind,
)
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreObjectTemplate
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.allocator import PoolAllocator


class NodeTemplateApplier:
    """Applies a template to produce field data for a new node."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, pool_allocator: PoolAllocator) -> None:
        self.db = db
        self.branch = branch
        self.pool_allocator = pool_allocator

    async def apply(
        self,
        template: CoreObjectTemplate,
        target_schema: MainSchemaTypes,  # noqa: ARG002
        target_id: str,
        user_fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply template and return merged fields. User fields take precedence."""
        fields = dict(user_fields)
        await self._apply_attributes(template=template, fields=fields)
        await self._apply_relationships(template=template, target_id=target_id, fields=fields)
        return fields

    async def _apply_attributes(self, template: CoreObjectTemplate, fields: dict[str, Any]) -> None:
        for attr_name in template.get_schema().attribute_names:
            if attr_name in fields or attr_name == OBJECT_TEMPLATE_NAME_ATTR:
                continue

            attr = template.get_attribute(name=attr_name)

            # Propagate from_pool reference for NumberPool attributes
            if attr.from_pool:
                fields[attr_name] = {"from_pool": attr.from_pool}
                continue

            if attr.value is not None:
                # source_id is dynamically set by NodePropertyMixin._init_node_property_mixin hence the type hint ignore
                field_data: dict[str, Any] = {"value": attr.value, "source": attr.source_id or template.id}  # type: ignore[attr-defined]
                if attr.is_from_profile:
                    field_data["is_from_profile"] = True
                fields[attr_name] = field_data

    async def _apply_relationships(self, template: CoreObjectTemplate, target_id: str, fields: dict[str, Any]) -> None:
        template_schema = template.get_schema()
        for rel_name in template_schema.relationship_names:
            rel_schema = template_schema.get_relationship(name=rel_name)

            if rel_name.endswith(RESOURCE_POOL_REL_SUFFIX):
                await self._handle_pool_relationship(
                    template=template, pool_rel_name=rel_name, target_id=target_id, fields=fields
                )
                continue

            if rel_name in fields:
                continue

            if rel_schema.kind not in [RelationshipKind.ATTRIBUTE, RelationshipKind.GENERIC, RelationshipKind.PROFILE]:
                continue

            if rel_name == OBJECT_TEMPLATE_RELATIONSHIP_NAME:
                continue

            relationship = template.get_relationship(name=rel_name)
            if rel_schema.cardinality == RelationshipCardinality.ONE:
                if peer := await relationship.get_peer(db=self.db):
                    fields[rel_name] = {"id": peer.id}
            elif peers := await relationship.get_peers(db=self.db):
                fields[rel_name] = [{"id": peer_id} for peer_id in peers]

    async def _handle_pool_relationship(
        self, template: CoreObjectTemplate, pool_rel_name: str, target_id: str, fields: dict[str, Any]
    ) -> None:
        """Allocate from pool and set the original relationship."""
        original_rel_name = pool_rel_name.removesuffix(RESOURCE_POOL_REL_SUFFIX)

        if original_rel_name in fields:
            return

        pool_relationship = template.get_relationship(name=pool_rel_name)
        allocated = await self.pool_allocator.allocate_for_relationship(
            pool_relationship=pool_relationship, identifier=target_id
        )

        if allocated:
            pool_node = await pool_relationship.get_peer(db=self.db, raise_on_error=True)
            fields[original_rel_name] = {"peer": allocated, "_relation__source": pool_node.id}

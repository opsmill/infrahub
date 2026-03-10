from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.exceptions import ValidationError

from .interface import RelationshipManagerConstraintInterface

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


class TemplateResourcePoolExclusiveConstraint(RelationshipManagerConstraintInterface):
    """Constraint that prevents setting both a relationship/attribute and its _from_resource_pool counterpart on templates.

    On template instances, users can either:
    - Set a fixed value (relationship peer or attribute value)
    - Set a pool to allocate from (e.g., ip_address_from_resource_pool or weight_from_resource_pool)

    But not both at the same time.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    def expand_filters(self, field_filters: list[str], node_schema: MainSchemaTypes) -> list[str]:
        if not node_schema.is_template_schema:
            return field_filters

        expanded = list(field_filters)
        for name in field_filters:
            pool_rel_name = f"{name}{RESOURCE_POOL_REL_SUFFIX}"
            if pool_rel_name in node_schema.relationship_names and pool_rel_name not in expanded:
                expanded.append(pool_rel_name)
        return expanded

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:
        if not node_schema.is_template_schema:
            return

        if not await self._relationship_has_peers(relm=relm):
            return

        rel_name = relm.schema.name

        if rel_name.endswith(RESOURCE_POOL_REL_SUFFIX):
            original_name = rel_name.removesuffix(RESOURCE_POOL_REL_SUFFIX)
            if original_name in node_schema.relationship_names:
                await self._check_counterpart_not_set(node=node, counterpart_name=original_name, current_name=rel_name)
            elif original_name in node_schema.attribute_names:
                self._check_attribute_counterpart_not_set(
                    node=node, attribute_name=original_name, current_name=rel_name
                )
        else:
            # Check if this relationship has a pool counterpart and if it's set
            pool_rel_name = f"{rel_name}{RESOURCE_POOL_REL_SUFFIX}"
            if pool_rel_name in node_schema.relationship_names:
                await self._check_counterpart_not_set(node=node, counterpart_name=pool_rel_name, current_name=rel_name)

    async def _relationship_has_peers(self, relm: RelationshipManager) -> bool:
        """Check if a relationship currently has peers (locally or untouched in DB)."""
        update_details = await relm.fetch_relationship_ids(db=self.db, force_refresh=True)
        peers_in_local_state = update_details.peer_ids_present_both or update_details.peer_ids_present_local_only
        peers_untouched_in_db = update_details.peer_ids_present_database_only and not relm.has_fetched_relationships
        return bool(peers_in_local_state or peers_untouched_in_db)

    async def _check_counterpart_not_set(self, node: Node, counterpart_name: str, current_name: str) -> None:
        """Check that the counterpart relationship is not set."""
        try:
            counterpart_relm = node.get_relationship(name=counterpart_name)
        except ValueError:
            return

        if await self._relationship_has_peers(relm=counterpart_relm):
            raise ValidationError(
                {
                    current_name: (
                        f"Cannot set '{current_name}' when '{counterpart_name}' is already set. "
                        "Templates can only use one of: direct relationship or resource pool allocation."
                    )
                }
            )

    @staticmethod
    def _check_attribute_counterpart_not_set(node: Node, attribute_name: str, current_name: str) -> None:
        """Check that the counterpart attribute does not have a user-set value."""
        try:
            attr = node.get_attribute(name=attribute_name)
        except ValueError:
            return

        if not attr.is_default and attr.value is not None:
            raise ValidationError(
                {
                    current_name: (
                        f"Cannot set '{current_name}' when '{attribute_name}' has a value set. "
                        "Templates can only use one of: direct attribute value or resource pool allocation."
                    )
                }
            )

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
    """Constraint that prevents setting both a relationship and its _from_resource_pool counterpart on templates.

    On template instances, users can either:
    - Set a fixed relationship value (e.g., ip_address pointing to a specific IP)
    - Set a pool to allocate from (e.g., ip_address_from_resource_pool pointing to a pool)

    But not both at the same time.
    """

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    async def check(self, relm: RelationshipManager, node_schema: MainSchemaTypes, node: Node) -> None:
        if not node_schema.is_template_schema:
            return

        rel_name = relm.schema.name

        if rel_name.endswith(RESOURCE_POOL_REL_SUFFIX):
            original_rel_name = rel_name.removesuffix(RESOURCE_POOL_REL_SUFFIX)
            await self._check_counterpart_not_set(node=node, counterpart_name=original_rel_name, current_name=rel_name)
        else:
            # Check if this relationship has a pool counterpart and if it's set
            pool_rel_name = f"{rel_name}{RESOURCE_POOL_REL_SUFFIX}"
            if pool_rel_name in node_schema.relationship_names:
                await self._check_counterpart_not_set(node=node, counterpart_name=pool_rel_name, current_name=rel_name)

    async def _check_counterpart_not_set(self, node: Node, counterpart_name: str, current_name: str) -> None:
        """Check that the counterpart relationship is not set."""
        try:
            counterpart_relm = node.get_relationship(name=counterpart_name)
        except ValueError:
            return

        update_details = await counterpart_relm.fetch_relationship_ids(db=self.db, force_refresh=True)

        # Counterpart has peers if local state has peers OR db peers exist and weren't cleared locally
        peers_in_local_state = update_details.peer_ids_present_both or update_details.peer_ids_present_local_only
        peers_untouched_in_db = (
            update_details.peer_ids_present_database_only and not counterpart_relm.has_fetched_relationships
        )

        if peers_in_local_state or peers_untouched_in_db:
            raise ValidationError(
                {
                    current_name: (
                        f"Cannot set '{current_name}' when '{counterpart_name}' is already set. "
                        "Templates can only use one of: direct relationship or resource pool allocation."
                    )
                }
            )

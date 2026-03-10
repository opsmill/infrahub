from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.node import Node
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.relationship.constraints.interface import RelationshipManagerConstraintInterface
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes


class NodeConstraintRunner:
    def __init__(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        uniqueness_constraint: NodeGroupedUniquenessConstraint,
        relationship_manager_constraints: list[RelationshipManagerConstraintInterface],
    ) -> None:
        self.db = db
        self.branch = branch
        self.uniqueness_constraint = uniqueness_constraint
        self.relationship_manager_constraints = relationship_manager_constraints

    async def check(
        self, node: Node, field_filters: list[str] | None = None, skip_uniqueness_check: bool = False
    ) -> None:
        async with self.db.start_session(read_only=False) as db:
            await node.resolve_relationships(db=db)

            if not skip_uniqueness_check:
                await self.uniqueness_constraint.check(node, filters=field_filters)

            node_schema = node.get_schema()
            effective_filters = self._expand_filters_for_pool_relationships(
                field_filters=field_filters, node_schema=node_schema
            )

            for relationship_name in node_schema.relationship_names:
                if effective_filters and relationship_name not in effective_filters:
                    continue
                relationship_manager: RelationshipManager = getattr(node, relationship_name)
                await relationship_manager.fetch_relationship_ids(db=db, force_refresh=True)
                for relationship_constraint in self.relationship_manager_constraints:
                    await relationship_constraint.check(relm=relationship_manager, node_schema=node_schema, node=node)

    @staticmethod
    def _expand_filters_for_pool_relationships(
        field_filters: list[str] | None, node_schema: "MainSchemaTypes"
    ) -> list[str] | None:
        """When an attribute is in field_filters and has a corresponding _from_resource_pool relationship,
        include that relationship in the filters so the exclusive constraint can run."""
        if not field_filters or not node_schema.is_template_schema:
            return field_filters

        expanded = list(field_filters)
        for name in field_filters:
            pool_rel_name = f"{name}{RESOURCE_POOL_REL_SUFFIX}"
            if pool_rel_name in node_schema.relationship_names and pool_rel_name not in expanded:
                expanded.append(pool_rel_name)
        return expanded

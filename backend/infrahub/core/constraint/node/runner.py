from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.relationship.constraints.interface import RelationshipManagerConstraintInterface
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.relationship.model import RelationshipManager


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
        async with self.db.start_session() as db:
            await node.resolve_relationships(db=db)

            if not skip_uniqueness_check:
                await self.uniqueness_constraint.check(node, filters=field_filters)

            for relationship_name in node.get_schema().relationship_names:
                if field_filters and relationship_name not in field_filters:
                    continue
                relationship_manager: RelationshipManager = getattr(node, relationship_name)
                await relationship_manager.fetch_relationship_ids(db=db, force_refresh=True)
                for relationship_constraint in self.relationship_manager_constraints:
                    await relationship_constraint.check(relm=relationship_manager, node_schema=node.get_schema())

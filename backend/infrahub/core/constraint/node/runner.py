from typing import TYPE_CHECKING, List, Optional

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.interface import NodeConstraintInterface
from infrahub.core.relationship.constraints.interface import RelationshipManagerConstraintInterface
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.relationship.model import RelationshipManager


class NodeConstraintRunner:
    def __init__(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        node_constraints: List[NodeConstraintInterface],
        relationship_manager_constraints: List[RelationshipManagerConstraintInterface],
    ) -> None:
        self.db = db
        self.branch = branch
        self.node_constraints = node_constraints
        self.relationship_manager_constraints = relationship_manager_constraints

    async def check(self, node: Node, field_filters: Optional[List[str]] = None) -> None:
        for node_constraint in self.node_constraints:
            await node_constraint.check(node, filters=field_filters)
        for relationship_name in node.get_schema().relationship_names:
            if field_filters and relationship_name not in field_filters:
                continue
            relationship_manager: RelationshipManager = getattr(node, relationship_name)
            for relationship_constraint in self.relationship_manager_constraints:
                await relationship_constraint.check(relationship_manager)

from typing import TYPE_CHECKING, Optional

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
        node_constraints: list[NodeConstraintInterface],
        relationship_manager_constraints: list[RelationshipManagerConstraintInterface],
    ) -> None:
        self.db = db
        self.branch = branch
        self.node_constraints = node_constraints
        self.relationship_manager_constraints = relationship_manager_constraints

    async def check(self, node: Node, field_filters: Optional[list[str]] = None) -> None:
        async with self.db.start_session() as db:
            await node.resolve_relationships(db=db)

            for node_constraint in self.node_constraints:
                await node_constraint.check(node, filters=field_filters)

            for relationship_name in node.get_schema().relationship_names:
                if field_filters and relationship_name not in field_filters:
                    continue
                relationship_manager: RelationshipManager = getattr(node, relationship_name)
                await relationship_manager.fetch_relationship_ids(db=db, force_refresh=True)
                for relationship_constraint in self.relationship_manager_constraints:
                    await relationship_constraint.check(relm=relationship_manager, node_schema=node.get_schema())

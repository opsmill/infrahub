from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
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

    async def check(self, node: Node, field_filters: list[str] | None = None) -> None:
        async with self.db.start_session() as db:
            await node.resolve_relationships(db=db)

            for relationship_name in node.get_schema().relationship_names:
                if field_filters and relationship_name not in field_filters:
                    continue
                relationship_manager: RelationshipManager = getattr(node, relationship_name)
                await relationship_manager.fetch_relationship_ids(db=db, force_refresh=True)
                for relationship_constraint in self.relationship_manager_constraints:
                    await relationship_constraint.check(relm=relationship_manager, node_schema=node.get_schema())

            if len(self.node_constraints) > 1 and not isinstance(
                self.node_constraints[-1], NodeGroupedUniquenessConstraint
            ):
                # If HFID constraint is the only constraint violated, all other constraints need to have ran,
                # as it means there is an existing node that we might want to update in the case of an upsert
                raise ValueError("Node constraint containing HFID check should be the last one to run")

            for node_constraint in self.node_constraints:
                await node_constraint.check(node, filters=field_filters)

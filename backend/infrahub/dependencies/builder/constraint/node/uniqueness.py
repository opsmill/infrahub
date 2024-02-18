from typing import Optional

from infrahub.core.branch import Branch
from infrahub.core.node.constraints.uniqueness import NodeUniquenessConstraint
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.interface import DependencyBuilder


class NodeUniquenessConstraintDependency(DependencyBuilder[NodeUniquenessConstraint]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> NodeUniquenessConstraint:
        return NodeUniquenessConstraint(db=db, branch=branch)

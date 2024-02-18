from typing import Optional

from infrahub.core.branch import Branch
from infrahub.core.relationship.constraints.count import RelationshipCountConstraint
from infrahub.database import InfrahubDatabase

from ....interface import DependencyBuilder


class RelationshipCountConstraintDependency(DependencyBuilder[RelationshipCountConstraint]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> RelationshipCountConstraint:
        return RelationshipCountConstraint(db=db, branch=branch)

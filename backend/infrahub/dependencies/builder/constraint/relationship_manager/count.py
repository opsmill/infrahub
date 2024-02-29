from infrahub.core.relationship.constraints.count import RelationshipCountConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipCountConstraintDependency(DependencyBuilder[RelationshipCountConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipCountConstraint:
        return RelationshipCountConstraint(db=context.db, branch=context.branch)

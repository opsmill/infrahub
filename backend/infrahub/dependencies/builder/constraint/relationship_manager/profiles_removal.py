from infrahub.core.relationship.constraints.profiles_removal import RelationshipProfileRemovalConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipProfileRemovalConstraintDependency(DependencyBuilder[RelationshipProfileRemovalConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipProfileRemovalConstraint:
        return RelationshipProfileRemovalConstraint(db=context.db, branch=context.branch)

from infrahub.core.relationship.constraints.peer_relatives import RelationshipRelativesConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipPeerRelativesConstraintDependency(DependencyBuilder[RelationshipRelativesConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipRelativesConstraint:
        return RelationshipRelativesConstraint(db=context.db, branch=context.branch)

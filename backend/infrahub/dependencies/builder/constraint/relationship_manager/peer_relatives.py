from infrahub.core.relationship.constraints.peer_relatives import RelationshipPeerRelativesConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipPeerRelativesConstraintDependency(DependencyBuilder[RelationshipPeerRelativesConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipPeerRelativesConstraint:
        return RelationshipPeerRelativesConstraint(db=context.db, branch=context.branch)

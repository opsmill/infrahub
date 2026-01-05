from infrahub.core.relationship.constraints.peer_parent import RelationshipPeerParentConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipPeerParentConstraintDependency(DependencyBuilder[RelationshipPeerParentConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipPeerParentConstraint:
        return RelationshipPeerParentConstraint(db=context.db, branch=context.branch)

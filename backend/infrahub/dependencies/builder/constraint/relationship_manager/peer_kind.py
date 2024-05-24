from infrahub.core.relationship.constraints.peer_kind import RelationshipPeerKindConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipPeerKindConstraintDependency(DependencyBuilder[RelationshipPeerKindConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipPeerKindConstraint:
        return RelationshipPeerKindConstraint(db=context.db, branch=context.branch)

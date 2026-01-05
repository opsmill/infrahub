from infrahub.core.validators.relationship.peer import RelationshipPeerParentChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaRelationshipPeerParentConstraintDependency(DependencyBuilder[RelationshipPeerParentChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipPeerParentChecker:
        return RelationshipPeerParentChecker(db=context.db, branch=context.branch)

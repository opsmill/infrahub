from infrahub.core.validators.relationship.peer import RelationshipPeerChecker, RelationshipPeerParentChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaRelationshipPeerConstraintDependency(DependencyBuilder[RelationshipPeerChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipPeerChecker:
        return RelationshipPeerChecker(db=context.db, branch=context.branch)


class SchemaRelationshipPeerParentConstraintDependency(DependencyBuilder[RelationshipPeerParentChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipPeerParentChecker:
        return RelationshipPeerParentChecker(db=context.db, branch=context.branch)

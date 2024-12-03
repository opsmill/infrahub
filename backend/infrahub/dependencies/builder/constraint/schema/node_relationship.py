from infrahub.core.validators.node.relationship import NodeRelationshipAddChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaNodeRelationshipAddConstraintDependency(DependencyBuilder[NodeRelationshipAddChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeRelationshipAddChecker:
        return NodeRelationshipAddChecker(db=context.db, branch=context.branch)

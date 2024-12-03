from infrahub.core.validators.node.attribute import NodeAttributeAddChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaNodeAttributeAddConstraintDependency(DependencyBuilder[NodeAttributeAddChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeAttributeAddChecker:
        return NodeAttributeAddChecker(db=context.db, branch=context.branch)

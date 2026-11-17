from infrahub.core.validators.node.hierarchy import NodeHierarchyChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaNodeHierarchyConstraintDependency(DependencyBuilder[NodeHierarchyChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeHierarchyChecker:
        return NodeHierarchyChecker(db=context.db, branch=context.branch)

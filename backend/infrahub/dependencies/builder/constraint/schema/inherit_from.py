from infrahub.core.validators.node.inherit_from import NodeInheritFromChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaInheritFromConstraintDependency(DependencyBuilder[NodeInheritFromChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeInheritFromChecker:
        return NodeInheritFromChecker(db=context.db, branch=context.branch)

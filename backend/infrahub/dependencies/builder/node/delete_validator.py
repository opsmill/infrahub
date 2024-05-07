from infrahub.core.node.delete_validator import NodeDeleteValidator
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class NodeDeleteValidatorDependency(DependencyBuilder[NodeDeleteValidator]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeDeleteValidator:
        return NodeDeleteValidator(db=context.db, branch=context.branch)

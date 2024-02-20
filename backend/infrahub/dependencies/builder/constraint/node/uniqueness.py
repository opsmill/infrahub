from infrahub.core.node.constraints.uniqueness import NodeUniquenessConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class NodeUniquenessConstraintDependency(DependencyBuilder[NodeUniquenessConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeUniquenessConstraint:
        return NodeUniquenessConstraint(db=context.db, branch=context.branch)

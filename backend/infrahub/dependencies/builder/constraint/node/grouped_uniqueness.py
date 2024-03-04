from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class NodeGroupedUniquenessConstraintDependency(DependencyBuilder[NodeGroupedUniquenessConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeGroupedUniquenessConstraint:
        return NodeGroupedUniquenessConstraint(db=context.db, branch=context.branch)

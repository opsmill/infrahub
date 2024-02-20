from infrahub.core.node.constraints.attribute_uniqueness import NodeAttributeUniquenessConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class NodeAttributeUniquenessConstraintDependency(DependencyBuilder[NodeAttributeUniquenessConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeAttributeUniquenessConstraint:
        return NodeAttributeUniquenessConstraint(db=context.db, branch=context.branch)

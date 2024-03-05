from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from ..node.grouped_uniqueness import NodeGroupedUniquenessConstraintDependency
from ..node.uniqueness import NodeAttributeUniquenessConstraintDependency
from ..relationship_manager.count import RelationshipCountConstraintDependency


class NodeConstraintRunnerDependency(DependencyBuilder[NodeConstraintRunner]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeConstraintRunner:
        return NodeConstraintRunner(
            db=context.db,
            branch=context.branch,
            node_constraints=[
                NodeAttributeUniquenessConstraintDependency.build(context=context),
                NodeGroupedUniquenessConstraintDependency.build(context=context),
            ],
            relationship_manager_constraints=[RelationshipCountConstraintDependency.build(context=context)],
        )

from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from ..node.grouped_uniqueness import NodeGroupedUniquenessConstraintDependency
from ..relationship_manager.count import RelationshipCountConstraintDependency
from ..relationship_manager.peer_kind import RelationshipPeerKindConstraintDependency
from ..relationship_manager.peer_relatives import RelationshipPeerRelativesConstraintDependency
from ..relationship_manager.profiles_kind import RelationshipProfilesKindConstraintDependency


class NodeConstraintRunnerDependency(DependencyBuilder[NodeConstraintRunner]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeConstraintRunner:
        return NodeConstraintRunner(
            db=context.db,
            branch=context.branch,
            uniqueness_constraint=NodeGroupedUniquenessConstraintDependency.build(context=context),
            relationship_manager_constraints=[
                RelationshipPeerKindConstraintDependency.build(context=context),
                RelationshipCountConstraintDependency.build(context=context),
                RelationshipProfilesKindConstraintDependency.build(context=context),
                RelationshipPeerRelativesConstraintDependency.build(context=context),
            ],
        )

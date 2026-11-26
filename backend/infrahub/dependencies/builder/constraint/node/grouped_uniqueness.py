from infrahub.core import registry
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.node.constraints.uniqueness_violation_message import UniquenessViolationMessageBuilder
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.pools.number_pool_conflict import NumberPoolConflictFinder
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.number_pool_usage_nodes import NumberHolderNodeReader


class NodeGroupedUniquenessConstraintDependency(DependencyBuilder[NodeGroupedUniquenessConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeGroupedUniquenessConstraint:
        schema_branch = registry.schema.get_schema_branch(context.branch.name)
        return NodeGroupedUniquenessConstraint(
            db=context.db,
            branch=context.branch,
            message_builder=UniquenessViolationMessageBuilder(schema_branch=schema_branch),
            number_pool_conflict_finder=NumberPoolConflictFinder(
                pool_name_reader=NumberPoolRepository(db=context.db),
                holder_reader=NumberHolderNodeReader(db=context.db),
            ),
        )

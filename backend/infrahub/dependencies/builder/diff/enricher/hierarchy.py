from infrahub.core.diff.enricher.hierarchy import DiffHierarchyEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from ..parent_node_adder import DiffParentNodeAdderDependency


class DiffHierarchyEnricherDependency(DependencyBuilder[DiffHierarchyEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffHierarchyEnricher:
        return DiffHierarchyEnricher(db=context.db, parent_adder=DiffParentNodeAdderDependency.build(context=context))

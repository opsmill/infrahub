from infrahub.core.diff.enricher.hierarchy import DiffHierarchyEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffHierarchyEnricherDependency(DependencyBuilder[DiffHierarchyEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffHierarchyEnricher:
        return DiffHierarchyEnricher(db=context.db)

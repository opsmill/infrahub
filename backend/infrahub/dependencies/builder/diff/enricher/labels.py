from infrahub.core.diff.enricher.labels import DiffLabelsEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffLabelsEnricherDependency(DependencyBuilder[DiffLabelsEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffLabelsEnricher:
        return DiffLabelsEnricher(db=context.db)

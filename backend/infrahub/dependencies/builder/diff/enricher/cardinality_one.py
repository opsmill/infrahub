from infrahub.core.diff.enricher.cardinality_one import DiffCardinalityOneEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffCardinalityOneEnricherDependency(DependencyBuilder[DiffCardinalityOneEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffCardinalityOneEnricher:
        return DiffCardinalityOneEnricher(db=context.db)

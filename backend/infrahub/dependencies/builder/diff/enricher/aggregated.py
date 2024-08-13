from infrahub.core.diff.enricher.aggregated import AggregatedDiffEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .cardinality_one import DiffCardinalityOneEnricherDependency
from .hierarchy import DiffHierarchyEnricherDependency


class DiffAggregatedEnricherDependency(DependencyBuilder[AggregatedDiffEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AggregatedDiffEnricher:
        return AggregatedDiffEnricher(
            enrichers=[
                DiffCardinalityOneEnricherDependency.build(context=context),
                DiffHierarchyEnricherDependency.build(context=context),
            ]
        )

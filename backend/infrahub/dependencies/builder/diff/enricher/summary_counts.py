from infrahub.core.diff.enricher.summary_counts import DiffSummaryCountsEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffSummaryCountsEnricherDependency(DependencyBuilder[DiffSummaryCountsEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffSummaryCountsEnricher:  # noqa: ARG003
        return DiffSummaryCountsEnricher()

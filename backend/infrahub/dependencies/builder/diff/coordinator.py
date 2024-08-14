from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .calculator import DiffCalculatorDependency
from .combiner import DiffCombinerDependency
from .conflicts_enricher import DiffConflictsEnricherDependency
from .enricher.aggregated import DiffAggregatedEnricherDependency
from .repository import DiffRepositoryDependency


class DiffCoordinatorDependency(DependencyBuilder[DiffCoordinator]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffCoordinator:
        return DiffCoordinator(
            diff_repo=DiffRepositoryDependency.build(context=context),
            diff_calculator=DiffCalculatorDependency.build(context=context),
            diff_combiner=DiffCombinerDependency.build(context=context),
            diff_enricher=DiffAggregatedEnricherDependency.build(context=context),
            conflicts_enricher=DiffConflictsEnricherDependency.build(context=context),
        )
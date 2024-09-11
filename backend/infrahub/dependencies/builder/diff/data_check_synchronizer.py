from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .conflicts_extractor import DiffConflictsExtractorDependency
from .data_check_conflict_recorder import DataCheckConflictRecorderDependency


class DiffDataCheckSynchronizerDependency(DependencyBuilder[DiffDataCheckSynchronizer]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffDataCheckSynchronizer:
        return DiffDataCheckSynchronizer(
            db=context.db,
            conflicts_extractor=DiffConflictsExtractorDependency.build(context=context),
            conflict_recorder=DataCheckConflictRecorderDependency.build(context=context),
        )

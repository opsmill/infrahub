from infrahub.core.diff.conflict_transferer import DiffConflictTransferer
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .combiner import DiffCombinerDependency


class DiffConflictTransfererDependency(DependencyBuilder[DiffConflictTransferer]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffConflictTransferer:
        return DiffConflictTransferer(diff_combiner=DiffCombinerDependency.build(context=context))

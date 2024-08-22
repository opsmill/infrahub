from infrahub.core.diff.conflicts_extractor import DiffConflictsExtractor
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffConflictsExtractorDependency(DependencyBuilder[DiffConflictsExtractor]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffConflictsExtractor:
        return DiffConflictsExtractor(db=context.db)

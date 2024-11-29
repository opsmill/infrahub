from infrahub.core.diff.conflicts_enricher import ConflictsEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffConflictsEnricherDependency(DependencyBuilder[ConflictsEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> ConflictsEnricher:
        return ConflictsEnricher()

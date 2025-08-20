from infrahub.core.diff.enricher.path_identifier import DiffPathIdentifierEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffPathIdentifierEnricherDependency(DependencyBuilder[DiffPathIdentifierEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffPathIdentifierEnricher:
        return DiffPathIdentifierEnricher(db=context.db)

from infrahub.core.diff.conflicts_enricher import ConflictsEnricher
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .managed_relationship_checker import ManagedRelationshipCheckerDependency


class DiffConflictsEnricherDependency(DependencyBuilder[ConflictsEnricher]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> ConflictsEnricher:
        return ConflictsEnricher(
            managed_relationship_checker=ManagedRelationshipCheckerDependency.build(context=context)
        )

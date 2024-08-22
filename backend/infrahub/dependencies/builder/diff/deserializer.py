from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffDeserializerDependency(DependencyBuilder[EnrichedDiffDeserializer]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> EnrichedDiffDeserializer:
        return EnrichedDiffDeserializer()

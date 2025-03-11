from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .parent_node_adder import DiffParentNodeAdderDependency


class DiffDeserializerDependency(DependencyBuilder[EnrichedDiffDeserializer]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> EnrichedDiffDeserializer:  # noqa: ARG003
        return EnrichedDiffDeserializer(parent_adder=DiffParentNodeAdderDependency.build(context=context))

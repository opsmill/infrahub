from infrahub.core.diff.combiner import DiffCombiner
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffCombinerDependency(DependencyBuilder[DiffCombiner]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffCombiner:  # noqa: ARG003
        return DiffCombiner()

from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffParentNodeAdderDependency(DependencyBuilder[DiffParentNodeAdder]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffParentNodeAdder:  # noqa: ARG003
        return DiffParentNodeAdder()

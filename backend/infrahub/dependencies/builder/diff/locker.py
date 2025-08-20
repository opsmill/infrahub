from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffLockerDependency(DependencyBuilder[DiffLocker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffLocker:  # noqa: ARG003
        return DiffLocker()

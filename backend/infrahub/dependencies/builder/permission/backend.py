from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.permissions.local_backend import LocalPermissionBackend


class PermissionLocalBackendDependency(DependencyBuilder[LocalPermissionBackend]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> LocalPermissionBackend:
        return LocalPermissionBackend(db=context.db, branch=context.branch)

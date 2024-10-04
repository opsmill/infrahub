import importlib

from infrahub import config
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.permissions.manager import PermissionManager


class PermissionManagerDependency(DependencyBuilder[PermissionManager]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> PermissionManager:
        backends: list[DependencyBuilder] = []
        for backend_module_path in config.SETTINGS.main.permission_backends:
            module_name, class_name = backend_module_path.rsplit(".", maxsplit=1)
            backends.append(
                context.component_registry.get_component(
                    component_class=getattr(importlib.import_module(module_name), class_name),
                    db=context.db,
                    branch=context.branch,
                )
            )

        return PermissionManager(backends=[backend.build(context=context) for backend in backends])

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from ..interface import DependencyBuilderContext
from .exceptions import UntrackedDependencyError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..interface import DependencyBuilder


T = TypeVar("T")


class ComponentDependencyRegistry:
    the_instance: Optional[ComponentDependencyRegistry] = None

    def __init__(self) -> None:
        self._available_components: dict[type, type[DependencyBuilder]] = {}
        self._cached_components: dict[type, Any] = {}

    @classmethod
    def get_registry(cls) -> ComponentDependencyRegistry:
        if not cls.the_instance:
            cls.the_instance = cls()
        return cls.the_instance

    async def get_component(self, component_class: type[T], db: InfrahubDatabase, branch: Branch) -> T:
        if component_class not in self._available_components:
            raise UntrackedDependencyError(f"'{component_class}' is not a tracked dependency")
        context = DependencyBuilderContext(db=db, branch=branch)
        return self._available_components[component_class].build(context=context)

    def cache_component(self, component: Any) -> None:
        self._cached_components[type(component)] = component

    def get_cached_component(self, component_class: type[T]) -> T:
        if component_class not in self._cached_components:
            raise UntrackedDependencyError(f"'{component_class}' is not a cached component")
        return self._cached_components[component_class]

    def track_dependency(self, dependency_class: type[DependencyBuilder]) -> None:
        signature = inspect.signature(dependency_class.build)
        returned_class = signature.return_annotation
        self._available_components[returned_class] = dependency_class

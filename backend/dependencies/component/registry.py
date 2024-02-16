import inspect
from typing import Any, Dict, TypeVar

from ..interface import DependencyBuilder
from .exceptions import UntrackedDependencyError

T = TypeVar("T")


class ComponentDependencyRegistry:
    def __init__(self) -> None:
        self._built_components: Dict[type, Any] = {}
        self._available_components: Dict[type, type[DependencyBuilder]] = {}

    def get_component(self, component_class: type[T]) -> T:
        if component_class not in self._built_components:
            component = self.build_component(component_class)
            self._built_components[component_class] = component
        return self._built_components[component_class]

    def build_component(self, component_class: type[T]) -> T:
        if component_class not in self._available_components:
            raise UntrackedDependencyError(f"'{component_class}' is not a tracked dependency")
        return self._available_components[component_class].build()

    def track_dependency(self, dependency_class: type[DependencyBuilder]) -> None:
        signature = inspect.signature(dependency_class.build)
        returned_class = signature.return_annotation
        self._available_components[returned_class] = dependency_class

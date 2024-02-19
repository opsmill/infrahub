from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Dict, Optional, TypeVar

from .exceptions import UntrackedDependencyError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..interface import DependencyBuilder


T = TypeVar("T")


class ComponentDependencyRegistry:
    the_instance: Optional[ComponentDependencyRegistry] = None

    def __init__(self) -> None:
        self._available_components: Dict[type, type[DependencyBuilder]] = {}

    @classmethod
    def get_registry(cls) -> ComponentDependencyRegistry:
        if not cls.the_instance:
            cls.the_instance = cls()
        return cls.the_instance

    def get_component(self, component_class: type[T], db: InfrahubDatabase, branch: Optional[Branch] = None) -> T:
        if component_class not in self._available_components:
            raise UntrackedDependencyError(f"'{component_class}' is not a tracked dependency")
        return self._available_components[component_class].build(db=db, branch=branch)

    def track_dependency(self, dependency_class: type[DependencyBuilder]) -> None:
        signature = inspect.signature(dependency_class.build)
        returned_class = signature.return_annotation
        self._available_components[returned_class] = dependency_class

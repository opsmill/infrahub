from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.dependencies.component.registry import ComponentDependencyRegistry

T = TypeVar("T")


@dataclass
class DependencyBuilderContext:
    component_registry: ComponentDependencyRegistry
    db: InfrahubDatabase
    branch: Branch


class DependencyBuilder(ABC, Generic[T]):
    @classmethod
    @abstractmethod
    def build(cls, context: DependencyBuilderContext) -> T: ...

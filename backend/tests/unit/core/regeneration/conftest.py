from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk import Config, InfrahubClient

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff


@pytest.fixture
def client() -> InfrahubClient:
    return InfrahubClient(config=Config(address="http://mock"))


@pytest.fixture
def log() -> logging.Logger:
    return logging.getLogger("test")


@dataclass(frozen=True, kw_only=True)
class DiffCase:
    """A node-id predicate case: whether the predicate fires for a given diff summary."""

    name: str
    diff: list[NodeDiff]
    expected: bool


@dataclass(frozen=True, kw_only=True)
class TransformChangedCase:
    """A file-closure predicate case: whether a repository file diff intersects the closure."""

    name: str
    dependencies: list[str] | None
    dependencies_complete: bool | None
    files_added: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    files_removed: list[str] = field(default_factory=list)
    expected: bool

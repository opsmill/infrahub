from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from infrahub.graph_traversal.planning.constants import (
    DEFAULT_EXCLUDED_NAMESPACES,
    MAX_DEPTH,
    MIN_DEPTH,
)


@dataclass(frozen=True, slots=True)
class TerminalById:
    node_id: str
    kind: str


@dataclass(frozen=True, slots=True)
class TerminalByKinds:
    kinds: frozenset[str]

    def __post_init__(self) -> None:
        if not self.kinds:
            raise ValueError("TerminalByKinds.kinds must be non-empty")


TerminalPredicate = TerminalById | TerminalByKinds


@dataclass(frozen=True, slots=True)
class UserFilters:
    kind_filter: frozenset[str] = field(default_factory=frozenset)
    excluded_kinds: frozenset[str] = field(default_factory=frozenset)
    excluded_namespaces: frozenset[str] = field(default_factory=lambda: frozenset(DEFAULT_EXCLUDED_NAMESPACES))
    relationship_filter: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_graphql_input(
        cls,
        data: Any,
    ) -> UserFilters:
        kind_filter = frozenset(getattr(data, "kind_filter", None) or ())
        excluded_kinds = frozenset(getattr(data, "excluded_kinds", None) or ())
        relationship_filter = frozenset(getattr(data, "relationship_filter", None) or ())

        excluded_namespaces = frozenset(DEFAULT_EXCLUDED_NAMESPACES)
        raw_excluded_namespaces = getattr(data, "excluded_namespaces", None)
        if raw_excluded_namespaces:
            excluded_namespaces |= frozenset(raw_excluded_namespaces)

        return cls(
            kind_filter=kind_filter,
            excluded_kinds=excluded_kinds,
            excluded_namespaces=excluded_namespaces,
            relationship_filter=relationship_filter,
        )


@dataclass(frozen=True, slots=True)
class Plan:
    """Schema-derived per-hop adjacency map plus the source/terminal/depth context.

    ``adjacency`` is ``{start_kind: {rel_name: frozenset(end_kind, ...)}}``: the
    set of ``(start_kind, rel_name, end_kind)`` triples that may appear on any
    ≤``max_depth`` path from ``source_kind`` to a kind matching
    ``terminal_predicate``.
    """

    adjacency: Mapping[str, Mapping[str, frozenset[str]]]
    source_kind: str
    terminal_predicate: TerminalPredicate
    max_depth: int

    def __post_init__(self) -> None:
        if not MIN_DEPTH <= self.max_depth <= MAX_DEPTH:
            raise ValueError(f"Plan.max_depth must be in [{MIN_DEPTH}, {MAX_DEPTH}], got {self.max_depth}")

    @property
    def is_empty(self) -> bool:
        return not self.adjacency

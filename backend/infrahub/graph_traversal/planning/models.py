from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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


@dataclass(slots=True)
class Plan:
    """Schema-derived per-hop adjacency map plus the source/terminal/depth context.

    Hops are added incrementally via ``add_hop``. The ``adjacency`` and
    ``min_depth_to_terminal`` accessors expose the accumulated structure as
    read-only mappings:

    - ``adjacency`` is ``{start_kind: {rel_name: frozenset(end_kind, ...)}}``: the
      set of ``(start_kind, rel_name, end_kind)`` triples that may appear on any
      ≤``max_depth`` path from ``source_kind`` to a kind matching
      ``terminal_predicate``.
    - ``min_depth_to_terminal`` is the per-kind minimum hop count to reach a
      terminal-matching end_kind through the accumulated adjacency.
    """

    source_kind: str
    terminal_predicate: TerminalPredicate
    max_depth: int
    _adjacency: dict[str, dict[str, set[str]]] = field(default_factory=dict, init=False, repr=False)
    _min_depth_to_terminal: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not MIN_DEPTH <= self.max_depth <= MAX_DEPTH:
            raise ValueError(f"Plan.max_depth must be in [{MIN_DEPTH}, {MAX_DEPTH}], got {self.max_depth}")

    def add_hop(
        self,
        source_kind: str,
        relationship_identifier: str,
        end_kind: str,
        min_hops_to_terminal: int,
    ) -> None:
        """Record a legal ``(source_kind, relationship_identifier, end_kind)`` triple.

        ``min_hops_to_terminal`` is the shortest hop count from ``end_kind`` to a
        terminal-matching kind through the plan's adjacency. Multiple calls for
        the same ``end_kind`` keep the smallest value seen.
        """
        self._adjacency.setdefault(source_kind, {}).setdefault(relationship_identifier, set()).add(end_kind)
        existing = self._min_depth_to_terminal.get(end_kind)
        if existing is None or min_hops_to_terminal < existing:
            self._min_depth_to_terminal[end_kind] = min_hops_to_terminal

    def get_min_depth_to_terminal_for_kind(self, kind: str) -> int | None:
        """Shortest hop count from ``kind`` to a terminal-matching kind, or ``None`` if unreachable."""
        return self._min_depth_to_terminal.get(kind)

    def get_relationship_map_for_kind(self, kind: str) -> dict[str, list[str]]:
        """Outgoing relationships and their destination kinds for ``kind``.

        Returns ``{relationship_identifier: [destination_kind, ...]}`` with destination
        kinds sorted. Empty dict if ``kind`` has no outgoing relationships.
        """
        return {rel_name: sorted(ends) for rel_name, ends in self._adjacency.get(kind, {}).items()}

    def get_kinds_within_hops_of_terminal(self, max_hops: int) -> list[str]:
        """Sorted list of kinds whose shortest hop count to a terminal-matching kind is ``<= max_hops``."""
        return sorted(kind for kind, dist in self._min_depth_to_terminal.items() if dist <= max_hops)

    def get_all_source_kinds(self) -> list[str]:
        """Sorted list of kinds that have at least one outgoing relationship recorded in this plan."""
        return sorted(self._adjacency)

    @property
    def is_empty(self) -> bool:
        return not self._adjacency or not self._min_depth_to_terminal

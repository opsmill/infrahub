from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from infrahub.graph_traversal.path import DEFAULT_EXCLUDED_NAMESPACES
from infrahub.graph_traversal.planning.constants import MAX_DEPTH, MIN_DEPTH


class HopDirection(IntEnum):
    OUTBOUND = 0
    INBOUND = 1
    BIDIR = 2


@dataclass(frozen=True, slots=True)
class Hop:
    start_kind: str
    end_kind: str
    relationship_identifier: str
    direction: HopDirection

    def __post_init__(self) -> None:
        if not self.relationship_identifier:
            raise ValueError("Hop.relationship_identifier must be non-empty")


@dataclass(frozen=True, slots=True)
class Route:
    hops: tuple[Hop, ...]
    source_kind: str
    terminal_kind: str

    def __post_init__(self) -> None:
        if not MIN_DEPTH <= len(self.hops) <= MAX_DEPTH:
            raise ValueError(f"Route.hops length must be in [{MIN_DEPTH}, {MAX_DEPTH}], got {len(self.hops)}")
        if self.hops[0].start_kind != self.source_kind:
            raise ValueError(
                f"Route.source_kind ({self.source_kind!r}) must equal hops[0].start_kind ({self.hops[0].start_kind!r})"
            )
        if self.hops[-1].end_kind != self.terminal_kind:
            raise ValueError(
                f"Route.terminal_kind ({self.terminal_kind!r}) must equal "
                f"hops[-1].end_kind ({self.hops[-1].end_kind!r})"
            )
        for i in range(1, len(self.hops)):
            if self.hops[i].start_kind != self.hops[i - 1].end_kind:
                raise ValueError(
                    f"Route hops are discontinuous at index {i}: "
                    f"hops[{i - 1}].end_kind={self.hops[i - 1].end_kind!r} but "
                    f"hops[{i}].start_kind={self.hops[i].start_kind!r}"
                )

    @property
    def length(self) -> int:
        return len(self.hops)

    @property
    def kinds(self) -> tuple[str, ...]:
        return (self.source_kind, *(hop.end_kind for hop in self.hops))


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
        *,
        default_excluded_namespaces: tuple[str, ...] = DEFAULT_EXCLUDED_NAMESPACES,
    ) -> UserFilters:
        kind_filter = frozenset(getattr(data, "kind_filter", None) or ())
        excluded_kinds = frozenset(getattr(data, "excluded_kinds", None) or ())
        relationship_filter = frozenset(getattr(data, "relationship_filter", None) or ())

        raw_excluded_namespaces = getattr(data, "excluded_namespaces", None)
        if raw_excluded_namespaces is None:
            excluded_namespaces = frozenset(default_excluded_namespaces)
        else:
            excluded_namespaces = frozenset(raw_excluded_namespaces)

        return cls(
            kind_filter=kind_filter,
            excluded_kinds=excluded_kinds,
            excluded_namespaces=excluded_namespaces,
            relationship_filter=relationship_filter,
        )


@dataclass(frozen=True, slots=True)
class Plan:
    routes: tuple[Route, ...]
    source_kind: str
    terminal_predicate: TerminalPredicate
    max_depth: int
    pruned_for_permission: tuple[Route, ...] = ()
    pruned_for_user_filters: tuple[Route, ...] = ()

    def __post_init__(self) -> None:
        if not MIN_DEPTH <= self.max_depth <= MAX_DEPTH:
            raise ValueError(f"Plan.max_depth must be in [{MIN_DEPTH}, {MAX_DEPTH}], got {self.max_depth}")
        overlap_a = set(self.routes) & set(self.pruned_for_permission)
        overlap_b = set(self.routes) & set(self.pruned_for_user_filters)
        overlap_c = set(self.pruned_for_permission) & set(self.pruned_for_user_filters)
        if overlap_a or overlap_b or overlap_c:
            raise ValueError(
                "Plan.routes, pruned_for_permission, and pruned_for_user_filters must be mutually exclusive"
            )

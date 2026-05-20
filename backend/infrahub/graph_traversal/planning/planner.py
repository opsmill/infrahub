from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.constants import RelationshipDirection
from infrahub.graph_traversal.planning.constants import MAX_DEPTH, MIN_DEPTH
from infrahub.graph_traversal.planning.models import (
    Hop,
    HopDirection,
    Plan,
    Route,
    TerminalById,
    TerminalPredicate,
    UserFilters,
)
from infrahub.graph_traversal.planning.permissions import KindPermissionCache

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.permissions.resolver import PermissionResolver


_DIRECTION_FROM_SCHEMA = {
    RelationshipDirection.OUTBOUND: HopDirection.OUTBOUND,
    RelationshipDirection.INBOUND: HopDirection.INBOUND,
    RelationshipDirection.BIDIR: HopDirection.BIDIR,
}

_DIRECTION_INVERTED = {
    HopDirection.OUTBOUND: HopDirection.INBOUND,
    HopDirection.INBOUND: HopDirection.OUTBOUND,
    HopDirection.BIDIR: HopDirection.BIDIR,
}


def _hop_direction_from_schema(direction: RelationshipDirection) -> HopDirection:
    return _DIRECTION_FROM_SCHEMA[direction]


def _invert_direction(direction: HopDirection) -> HopDirection:
    """Flip a Hop's direction for reverse traversal."""
    return _DIRECTION_INVERTED[direction]


@dataclass(frozen=True, slots=True)
class _FrontierEntry:
    """One in-flight BFS branch during route enumeration.

    ``visited_intermediates`` contains every kind on this path except the
    source.
    """

    current_kind: str
    hops_so_far: tuple[Hop, ...]
    visited_intermediates: frozenset[str]


class SchemaPlanner:
    """Enumerates schema-derived routes between kinds and prunes them by
    user-supplied filters and the requester's view permissions.

    Synchronous and stateless from the outside: every public dependency
    (schema view, branch, permission resolver) is injected at construction
    time. ``plan()`` is callable any number of times.
    """

    def __init__(
        self,
        *,
        schema_branch: SchemaBranch,
        branch: Branch,
        permission_resolver: PermissionResolver,
    ) -> None:
        self._schema_branch = schema_branch
        self._branch = branch
        self._permission_cache = KindPermissionCache(
            resolver=permission_resolver,
            branch=branch,
            schema_branch=schema_branch,
        )

        self._relationships_cache: dict[str, tuple[tuple[str, str, HopDirection], ...]] = {}
        self._concrete_cache: dict[str, tuple[str, ...]] = {}
        self._namespace_cache: dict[str, str] = {}
        self._inverse_index: dict[str, list[tuple[str, RelationshipSchema]]] | None = None

    def _kind_exists(self, kind: str) -> bool:
        return kind in self._schema_branch.nodes or kind in self._schema_branch.generics

    def _concrete_kinds_for(self, kind: str) -> tuple[str, ...]:
        """Expand a (possibly generic) kind to the tuple of concrete kinds.

        Concrete kinds expand to a single-element tuple. Generic kinds expand
        via ``GenericSchema.used_by`` directly.
        """
        cached = self._concrete_cache.get(kind)
        if cached is not None:
            return cached
        if kind in self._schema_branch.generics:
            generic = self._schema_branch.get_generic(name=kind, duplicate=False)
            kinds_used_by = tuple(sorted(generic.used_by))
        else:
            kinds_used_by = (kind,)
        self._concrete_cache[kind] = kinds_used_by
        return kinds_used_by

    def _namespace_for(self, kind: str) -> str:
        cached = self._namespace_cache.get(kind)
        if cached is not None:
            return cached
        namespace = self._schema_branch.get(name=kind, duplicate=False).namespace
        self._namespace_cache[kind] = namespace
        return namespace

    def _get_inverse_index(self) -> dict[str, list[tuple[str, RelationshipSchema]]]:
        """Get or build map from peer kind to [(owner kind, RelationshipSchema), ...].

        Required because schema relationships are declared once on the owning
        kind but planner enumeration walks bidirectionally. Iterates concrete
        node kinds in alphabetical order so the cache build is deterministic.
        Inherited relationships are already materialized on each concrete
        kind's ``.relationships``, so iterating generics is unnecessary.
        """
        if self._inverse_index is not None:
            return self._inverse_index
        self._inverse_index = {}
        for owner_kind in sorted(self._schema_branch.nodes):
            schema = self._schema_branch.get_node(name=owner_kind, duplicate=False)
            for rel in schema.relationships:
                for concrete_peer in self._concrete_kinds_for(rel.peer):
                    self._inverse_index.setdefault(concrete_peer, []).append((owner_kind, rel))
        return self._inverse_index

    def _relationships_for(self, kind: str) -> tuple[tuple[str, str, HopDirection], ...]:
        """Return every ``(peer_kind, identifier, direction)`` reachable from ``kind``.

        Combines forward traversal (``kind``'s outgoing relationships) with
        reverse traversal (other kinds that have ``kind`` as a peer, sourced
        from the inverse index). Generic peers are expanded to concrete kinds
        via ``_concrete_kinds_for``. Entries are deduplicated and sorted so the
        planner's output is deterministic across invocations.
        """
        cached = self._relationships_cache.get(kind)
        if cached is not None:
            return cached

        entries: set[tuple[str, str, HopDirection]] = set()

        if kind in self._schema_branch.nodes:
            schema = self._schema_branch.get_node(name=kind, duplicate=False)
            for rel in schema.relationships:
                direction = _hop_direction_from_schema(rel.direction)
                entries.update(
                    (concrete_peer, rel.get_identifier(), direction)
                    for concrete_peer in self._concrete_kinds_for(rel.peer)
                )

        for owner_kind, rel in self._get_inverse_index().get(kind, []):
            direction = _invert_direction(_hop_direction_from_schema(rel.direction))
            entries.add((owner_kind, rel.get_identifier(), direction))

        self._relationships_cache[kind] = tuple(sorted(entries))
        return self._relationships_cache[kind]

    def plan(
        self,
        *,
        source_kind: str,
        terminal_predicate: TerminalPredicate,
        max_depth: int,
        user_filters: UserFilters,
    ) -> Plan:
        if not MIN_DEPTH <= max_depth <= MAX_DEPTH:
            raise ValueError(f"max_depth must be in [{MIN_DEPTH}, {MAX_DEPTH}], got {max_depth}")
        if not self._kind_exists(source_kind):
            raise ValueError(f"source_kind {source_kind!r} not in schema")
        if isinstance(terminal_predicate, TerminalById):
            if not self._kind_exists(terminal_predicate.kind):
                raise ValueError(f"terminal kind {terminal_predicate.kind!r} not in schema")
        else:
            for k in terminal_predicate.kinds:
                if not self._kind_exists(k):
                    raise ValueError(f"terminal kind {k!r} not in schema")

        if not self._permission_cache.can_view(source_kind):
            candidates: list[Route] = []
        else:
            candidates = self._enumerate_routes(
                source_kind=source_kind,
                terminal_predicate=terminal_predicate,
                max_depth=max_depth,
                user_filters=user_filters,
            )

        sorted_routes = tuple(sorted(candidates, key=_route_sort_key))

        return Plan(
            routes=sorted_routes,
            source_kind=source_kind,
            terminal_predicate=terminal_predicate,
            max_depth=max_depth,
        )

    def _enumerate_routes(
        self,
        *,
        source_kind: str,
        terminal_predicate: TerminalPredicate,
        max_depth: int,
        user_filters: UserFilters,
    ) -> list[Route]:
        """Iterative BFS up to ``max_depth``.

        Each frontier entry carries the set of kinds already on its path
        excluding the source (positions ``1..len(hops_so_far)`` of the path,
        i.e. the current kind plus all preceding intermediates). When
        ``allow_schema_revisits`` is ``False``, a candidate peer kind that
        appears in that set, or that equals the source kind without also
        being a valid terminal, is dropped before any work is done; the BFS
        therefore never explores cyclic branches in the first place.

        When ``allow_schema_revisits`` is ``True``, a kind may appear multiple
        times along a route — only the total hop count is bounded, so cyclic
        schemas produce multiple routes that revisit the same kinds within
        the depth cap.

        ``user_filters`` is consulted inside ``_step`` so excluded peers
        prune the entire downstream subtree.
        """
        candidates: list[Route] = []
        frontiers: list[_FrontierEntry] = [
            _FrontierEntry(current_kind=source_kind, hops_so_far=(), visited_intermediates=frozenset())
        ]
        while frontiers:
            next_frontiers: list[_FrontierEntry] = []
            for entry in frontiers:
                for peer_kind, identifier, direction in self._relationships_for(entry.current_kind):
                    route, next_entry = self._step(
                        entry=entry,
                        peer_kind=peer_kind,
                        identifier=identifier,
                        direction=direction,
                        source_kind=source_kind,
                        terminal_predicate=terminal_predicate,
                        max_depth=max_depth,
                        user_filters=user_filters,
                    )
                    if route is not None:
                        candidates.append(route)
                    if next_entry is not None:
                        next_frontiers.append(next_entry)
            frontiers = next_frontiers
        return candidates

    def _step(
        self,
        *,
        entry: _FrontierEntry,
        peer_kind: str,
        identifier: str,
        direction: HopDirection,
        source_kind: str,
        terminal_predicate: TerminalPredicate,
        max_depth: int,
        user_filters: UserFilters,
    ) -> tuple[Route | None, _FrontierEntry | None]:
        """Process one ``(entry, candidate peer)`` pair during BFS enumeration.

        Returns ``(route_or_none, next_entry_or_none)``: a route emitted by
        this step (if the peer matches the terminal predicate), and the
        next-frontier entry to continue expanding from (if depth, revisit,
        and filter rules permit). Either or both may be ``None``.

        Filter semantics applied here:

        - **Permissions**: if the requester can't view the peer kind, drop
          the subtree.
        - ``excluded_namespaces``, ``excluded_kinds``, ``relationship_filter``:
          no exemption. If the peer (or this hop's identifier) violates one
          of these, the entire subtree is dropped.
        - ``kind_filter``: source and terminal are exempt. If the peer is not
          in ``kind_filter`` AND does not match the terminal predicate, drop
          the subtree. If it does match the terminal, emit the route but do
          not extend.
        """
        allow_schema_revisits = user_filters.allow_schema_revisits
        is_pruned = False

        if not allow_schema_revisits and peer_kind in entry.visited_intermediates:
            # Intermediate revisit — pruning here removes the entire downstream subtree.
            is_pruned = True

        # Permission prune. ``KindPermissionCache`` memoizes per kind, so
        # repeated checks across BFS frontier entries are O(1) lookups.
        elif not self._permission_cache.can_view(peer_kind):
            is_pruned = True

        # No-exemption filter prunes. Dropping a peer here also drops every
        # route that would have continued through it, which is the whole
        # point — schemas with large excluded namespaces fan out exponentially.
        elif user_filters.excluded_kinds and peer_kind in user_filters.excluded_kinds:
            is_pruned = True
        elif user_filters.excluded_namespaces and self._namespace_for(peer_kind) in user_filters.excluded_namespaces:
            is_pruned = True
        elif user_filters.relationship_filter and identifier not in user_filters.relationship_filter:
            is_pruned = True

        matches_terminal = _matches_terminal(peer_kind, terminal_predicate)
        peer_allowed_as_intermediate = not user_filters.kind_filter or peer_kind in user_filters.kind_filter
        if not peer_allowed_as_intermediate and not matches_terminal:
            is_pruned = True

        if is_pruned:
            return None, None

        new_hop = Hop(
            start_kind=entry.current_kind,
            end_kind=peer_kind,
            relationship_identifier=identifier,
            direction=direction,
        )
        new_hops = (*entry.hops_so_far, new_hop)

        route: Route | None = None
        if matches_terminal:
            route = Route(hops=new_hops, source_kind=source_kind, terminal_kind=peer_kind)

        if len(new_hops) >= max_depth:
            return route, None
        if not allow_schema_revisits and peer_kind == source_kind:
            # Source kind at terminal position is allowed above; prevent paths
            # that would put the source kind in an intermediate position.
            return route, None
        if not peer_allowed_as_intermediate:
            # Peer is only allowed via the terminal exemption; extending would
            # turn it into an intermediate of a longer route.
            return route, None

        # The peer becomes the new current; record it so any further revisit
        # of the same kind (including a subsequent self-loop) is pruned.
        next_entry = _FrontierEntry(
            current_kind=peer_kind,
            hops_so_far=new_hops,
            visited_intermediates=entry.visited_intermediates | {peer_kind},
        )
        return route, next_entry


def _matches_terminal(kind: str, terminal_predicate: TerminalPredicate) -> bool:
    if isinstance(terminal_predicate, TerminalById):
        return kind == terminal_predicate.kind
    return kind in terminal_predicate.kinds


def _route_sort_key(route: Route) -> tuple[int, tuple[str, ...], tuple[str, ...], tuple[int, ...]]:
    """Deterministic lexicographic sort key for surviving routes."""
    return (
        route.length,
        route.kinds,
        tuple(hop.relationship_identifier for hop in route.hops),
        tuple(int(hop.direction) for hop in route.hops),
    )

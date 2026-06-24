from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.graph_traversal.planning.constants import DEFAULT_EXCLUDED_KINDS, MAX_DEPTH, MIN_DEPTH
from infrahub.graph_traversal.planning.models import (
    Plan,
    TerminalById,
    TerminalByKinds,
    TerminalPredicate,
    UserFilters,
)
from infrahub.graph_traversal.planning.permissions import KindPermissionCache

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import RelationshipSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.permissions.resolver import PermissionResolver


class SchemaPlanner:
    """Builds the per-hop adjacency map of legal ``(start_kind, rel_name, end_kind)`` triples.

    Triples are produced for a single source/terminal/depth query, pruned by user filters and
    the requester's view permissions.

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

        self._relationships_cache: dict[str, tuple[tuple[str, str], ...]] = {}
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

    def _relationships_for(self, kind: str) -> tuple[tuple[str, str], ...]:
        """Return every ``(peer_kind, identifier)`` reachable from ``kind``.

        Combines forward traversal (``kind``'s outgoing relationships) with
        reverse traversal (other kinds that have ``kind`` as a peer, sourced
        from the inverse index). Generic peers are expanded to concrete kinds
        via ``_concrete_kinds_for``. Entries are deduplicated and sorted so the
        planner's output is deterministic across invocations.
        """
        cached = self._relationships_cache.get(kind)
        if cached is not None:
            return cached

        entries: set[tuple[str, str]] = set()

        if kind in self._schema_branch.nodes:
            schema = self._schema_branch.get_node(name=kind, duplicate=False)
            for rel in schema.relationships:
                entries.update(
                    (concrete_peer, rel.get_identifier()) for concrete_peer in self._concrete_kinds_for(rel.peer)
                )

        entries.update(
            (owner_kind, rel.get_identifier()) for owner_kind, rel in self._get_inverse_index().get(kind, [])
        )

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
        for k in user_filters.kind_filter:
            if not self._kind_exists(k):
                raise ValueError(f"kind_filter kind {k!r} not in schema")
        for k in user_filters.excluded_kinds:
            if not self._kind_exists(k):
                raise ValueError(f"excluded_kinds kind {k!r} not in schema")
        for k in user_filters.included_kinds:
            if not self._kind_exists(k):
                raise ValueError(f"included_kinds kind {k!r} not in schema")

        terminal_predicate = self._expand_generic_kinds_in_terminal(terminal_predicate)
        user_filters = self._expand_generic_kinds_in_filters(user_filters)

        new_plan = Plan(
            source_kind=source_kind,
            terminal_predicate=terminal_predicate,
            max_depth=max_depth,
            excluded_kinds=user_filters.excluded_kinds,
        )
        if not self._permission_cache.can_view(source_kind):
            return new_plan

        self._populate_plan(plan=new_plan, terminal_predicate=terminal_predicate, user_filters=user_filters)
        return new_plan

    def _expand_to_concretes(self, kinds: frozenset[str]) -> frozenset[str]:
        """Replace each generic in ``kinds`` with its concrete implementors."""
        return frozenset(concrete for k in kinds for concrete in self._concrete_kinds_for(k))

    def _expand_generic_kinds_in_terminal(self, terminal_predicate: TerminalPredicate) -> TerminalPredicate:
        if isinstance(terminal_predicate, TerminalByKinds):
            expanded = self._expand_to_concretes(terminal_predicate.kinds)
            if expanded != terminal_predicate.kinds:
                return TerminalByKinds(kinds=expanded)
        return terminal_predicate

    def _expand_generic_kinds_in_filters(self, user_filters: UserFilters) -> UserFilters:
        """Expand generics to concretes and fold the default exclusions into ``excluded_kinds``.

        The effective exclusions are the requested ones plus the defaults;
        ``included_kinds`` subtracts from the defaults only, so an explicitly
        requested exclusion always wins.
        """
        expanded_kind_filter = (
            self._expand_to_concretes(user_filters.kind_filter)
            if user_filters.kind_filter
            else user_filters.kind_filter
        )
        effective_excluded_kinds = self._expand_to_concretes(user_filters.excluded_kinds) | (
            self._expand_to_concretes(frozenset(DEFAULT_EXCLUDED_KINDS))
            - self._expand_to_concretes(user_filters.included_kinds)
        )
        return UserFilters(
            kind_filter=expanded_kind_filter,
            excluded_kinds=effective_excluded_kinds,
            included_kinds=user_filters.included_kinds,
            excluded_namespaces=user_filters.excluded_namespaces,
            relationship_filter=user_filters.relationship_filter,
        )

    def _populate_plan(
        self,
        *,
        plan: Plan,
        terminal_predicate: TerminalPredicate,
        user_filters: UserFilters,
    ) -> None:
        """Add every legal source→terminal hop within ``plan.max_depth`` to ``plan``.

        Three passes:

        1. Forward BFS from ``plan.source_kind`` records every legal
           ``(start, rel, end)`` hop and the min hops from source to each
           kind. Filters and permissions are applied per-hop.
        2. Reverse BFS from terminal-matching kinds computes the min hops
           from each kind back to a terminal. If no kind reaches a terminal,
           the plan stays empty.
        3. For every forward hop whose total length
           ``d_from_source[start] + 1 + d_to_terminal[end] ≤ plan.max_depth``,
           call ``plan.add_hop``.
        """
        forward, min_depth_from_source = self._forward_bfs(
            source_kind=plan.source_kind,
            terminal_predicate=terminal_predicate,
            max_depth=plan.max_depth,
            user_filters=user_filters,
        )
        min_depth_to_terminal = _min_depth_to_terminal(forward=forward, terminal_predicate=terminal_predicate)
        if not min_depth_to_terminal:
            return
        _add_hops_within_depth(
            plan=plan,
            forward=forward,
            min_depth_from_source=min_depth_from_source,
            min_depth_to_terminal=min_depth_to_terminal,
        )

    def _forward_bfs(
        self,
        *,
        source_kind: str,
        terminal_predicate: TerminalPredicate,
        max_depth: int,
        user_filters: UserFilters,
    ) -> tuple[dict[str, dict[str, set[str]]], dict[str, int]]:
        """Pass 1: forward BFS from ``source_kind``.

        Returns ``(forward, min_depth_from_source)`` where ``forward`` is the
        unfiltered ``{start: {rel: {end, ...}}}`` adjacency of every legal
        hop reachable within ``max_depth``. The ``kind_filter`` terminal
        exemption is preserved: a peer that matches the terminal predicate
        is recorded even when not in the filter, but is not extended.
        """
        forward: dict[str, dict[str, set[str]]] = {}
        min_depth_from_source: dict[str, int] = {source_kind: 0}
        frontier: set[str] = {source_kind}
        for current_depth in range(max_depth):
            next_frontier: set[str] = set()
            for kind in frontier:
                for peer_kind, identifier in self._relationships_for(kind):
                    extendable = self._record_hop_if_allowed(
                        forward=forward,
                        start=kind,
                        identifier=identifier,
                        peer_kind=peer_kind,
                        terminal_predicate=terminal_predicate,
                        user_filters=user_filters,
                    )
                    if extendable and peer_kind not in min_depth_from_source:
                        min_depth_from_source[peer_kind] = current_depth + 1
                        next_frontier.add(peer_kind)
            frontier = next_frontier
        return forward, min_depth_from_source

    def _record_hop_if_allowed(
        self,
        *,
        forward: dict[str, dict[str, set[str]]],
        start: str,
        identifier: str,
        peer_kind: str,
        terminal_predicate: TerminalPredicate,
        user_filters: UserFilters,
    ) -> bool:
        """Apply per-hop filters; record the hop if it survives.

        Returns ``True`` iff the peer is extendable (i.e. allowed as an
        intermediate of a longer path). A peer admitted only via the
        ``kind_filter`` terminal exemption is recorded but not extendable.
        """
        if not self._permission_cache.can_view(peer_kind):
            return False
        if user_filters.excluded_kinds and peer_kind in user_filters.excluded_kinds:
            return False
        if user_filters.excluded_namespaces and self._namespace_for(peer_kind) in user_filters.excluded_namespaces:
            return False
        if user_filters.relationship_filter and identifier not in user_filters.relationship_filter:
            return False

        matches_terminal = _matches_terminal(peer_kind, terminal_predicate)
        in_kind_filter = not user_filters.kind_filter or peer_kind in user_filters.kind_filter
        if not in_kind_filter and not matches_terminal:
            return False

        forward.setdefault(start, {}).setdefault(identifier, set()).add(peer_kind)
        return in_kind_filter


def _matches_terminal(kind: str, terminal_predicate: TerminalPredicate) -> bool:
    if isinstance(terminal_predicate, TerminalById):
        return kind == terminal_predicate.kind
    return kind in terminal_predicate.kinds


def _min_depth_to_terminal(
    *,
    forward: dict[str, dict[str, set[str]]],
    terminal_predicate: TerminalPredicate,
) -> dict[str, int]:
    """Pass 2: reverse BFS through ``forward`` from terminal-matching kinds.

    Returns ``{kind: min hops to reach a terminal-matching end_kind}``. If no
    edge ends at a terminal-matching kind, returns an empty dict, meaning no
    paths exist.
    """
    terminal_kinds = {
        end_kind
        for rels in forward.values()
        for ends in rels.values()
        for end_kind in ends
        if _matches_terminal(end_kind, terminal_predicate)
    }
    if not terminal_kinds:
        return {}

    reverse_edges: dict[str, set[str]] = {}
    for start, rels in forward.items():
        for ends in rels.values():
            for end in ends:
                reverse_edges.setdefault(end, set()).add(start)

    min_depth: dict[str, int] = dict.fromkeys(terminal_kinds, 0)
    frontier: set[str] = set(terminal_kinds)
    while frontier:
        next_frontier: set[str] = set()
        for kind in frontier:
            candidate_depth = min_depth[kind] + 1
            for prev_kind in reverse_edges.get(kind, ()):
                if prev_kind not in min_depth or candidate_depth < min_depth[prev_kind]:
                    min_depth[prev_kind] = candidate_depth
                    next_frontier.add(prev_kind)
        frontier = next_frontier
    return min_depth


def _add_hops_within_depth(
    *,
    plan: Plan,
    forward: dict[str, dict[str, set[str]]],
    min_depth_from_source: dict[str, int],
    min_depth_to_terminal: dict[str, int],
) -> None:
    """Pass 3: add every forward hop on some ≤``plan.max_depth`` source→terminal path to ``plan``."""
    max_depth = plan.max_depth
    for start, rels in forward.items():
        d_from_source = min_depth_from_source[start]
        for identifier, ends in rels.items():
            for end in ends:
                d_to_terminal = min_depth_to_terminal.get(end)
                if d_to_terminal is not None and d_from_source + 1 + d_to_terminal <= max_depth:
                    plan.add_hop(
                        source_kind=start,
                        relationship_identifier=identifier,
                        end_kind=end,
                        min_hops_to_terminal=d_to_terminal,
                    )

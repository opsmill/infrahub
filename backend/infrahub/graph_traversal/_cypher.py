"""Cypher renderer for the graph-traversal planner.

Two terminal predicates are served by separate entry points:

- ``TerminalById`` is served by a bidirectional ("meet-in-the-middle") search the
  caller orchestrates: ``render_bfs`` expands a node-bounded BFS frontier inward from
  each anchor (all hops in one query) to build a per-node shortest-distance map, and
  ``render_canonical_join`` reconstructs the shortest paths of one depth tier through
  the candidate middle nodes. This avoids the exponential path enumeration of a single
  deep ``SHORTEST k`` search to a specific target.

- ``TerminalByKinds`` is split into two renders so the caller can discover
  terminals once and then enumerate paths depth-by-depth:

  - ``render_reachable_targets``: per-depth chained ``DISTINCT`` CALLs discover
    up to ``$max_targets`` distinct terminal vertices. Inter-CALL
    ``ORDER BY kind, uuid LIMIT $max_targets`` clauses bound intermediate
    cardinality. Returns ``collect(target.uuid) AS terminal_uuids``.
  - ``render_paths_to_targets``: per-depth fixed-length ``MATCH`` queries
    anchored on ``source`` and ``target.uuid IN $terminal_uuids`` (a bound
    parameter) enumerate paths to the discovered terminals, bounded by
    ``$max_paths`` and an optional ``depths`` restriction.

Branch-conditional pieces:

- Edge visibility is branch/time-aware (see ``_BRANCH_VISIBLE``): edges on the queried
  branch (or global) are visible at ``$at``; edges on the default branch (or global) are
  visible at ``$default_time`` — the branch's fork time (``branched_from``), so
  default-branch edges created after the fork are excluded. On the default branch both
  clauses collapse to ``$at``.
- On a user branch each hop in both phases gets two ``NOT EXISTS`` deletion-shadow checks
  (one for each side of the ``Relationship`` vertex) and the query binds ``$user_branch``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.timestamp import Timestamp
from infrahub.graph_traversal.planning.models import Plan, TerminalById

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.branch import Branch


def _terminal_kinds_for_plan(plan: Plan) -> frozenset[str]:
    if isinstance(plan.terminal_predicate, TerminalById):
        return frozenset({plan.terminal_predicate.kind})
    return plan.terminal_predicate.kinds


def _legal_triples(plan: Plan) -> list[list[str]]:
    """Every schema-legal ``[start_kind, rel_name, end_kind]`` hop in the plan's adjacency."""
    triples: set[tuple[str, str, str]] = set()
    for kind in plan.get_all_source_kinds():
        for rel_name, ends in plan.get_relationship_map_for_kind(kind).items():
            triples.update((kind, rel_name, end) for end in ends)
    return [list(t) for t in sorted(triples)]


def _legal_triples_reversed(plan: Plan) -> list[list[str]]:
    """``_legal_triples`` with each hop reversed: ``[end_kind, rel_name, start_kind]``.

    A backward frontier expansion walks from the destination toward the source, so an
    edge that is legal as ``[start, rel, end]`` in source→destination order is matched
    from the other side as ``[end, rel, start]``.
    """
    return [[end, rel, start] for start, rel, end in _legal_triples(plan)]


class HopTuple(NamedTuple):
    """A legal ``(start_kind, relationship_identifier, end_kind)`` schema hop."""

    start_kind: str
    relationship_identifier: str
    end_kind: str


_RETURN_LABELS: tuple[str, ...] = ("start_node_uuid", "start_node_kind", "hops", "depth")
_TARGETS_RETURN_LABELS: tuple[str, ...] = ("terminal_uuids",)

_MAX_TARGETS_MINIMUM = 1
_MAX_TARGETS_MAXIMUM = 200

_MAX_PATHS_MINIMUM = 1
_MAX_PATHS_MAXIMUM = 5000


@dataclass(frozen=True, slots=True)
class RenderedCypher:
    text: str
    params: dict[str, Any]
    return_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _QppVars:
    """Cypher variable names for one quantified-path-pattern hop ``(start)-[edge_in]-(rel)-[edge_out]-(end)``.

    The two halves of the canonical join need disjoint names because Neo4j forbids reusing
    a QPP-local variable across separate MATCH clauses.
    """

    start: str
    edge_in: str
    rel: str
    edge_out: str
    end: str


@dataclass(frozen=True, slots=True)
class _DepthRenderData:
    """Pre-computed data for rendering one fixed-depth query (Phase 1 or Phase 2).

    ``per_step_kinds[k - 1]`` lists the kinds allowed at intermediate position
    ``k`` (positions 1..depth-1); empty for depth-1 paths.

    ``tuples_per_hop[h - 1]`` is the list of legal ``(start_kind, rel_name, end_kind)``
    schema hops at edge position ``h`` (1..depth) — derived from the planner's
    adjacency restricted to the per-position kind sets.
    """

    depth: int
    per_step_kinds: list[list[str]]
    tuples_per_hop: list[list[HopTuple]]

    def hop_tuple_param(self, hop: int) -> str:
        """Cypher parameter name carrying the legal triples for the ``hop``-th edge."""
        return f"hop_tuples_d{self.depth}_h{hop}"


# Branch/time visibility for one edge variable, without a status check. Two clauses, one per
# (branch-set, cutoff-time) pair, mirroring ``Branch.get_query_filter_path``:
#   - ``$at_branches`` = [global, queried-branch]; these edges are visible up to ``$at`` (now).
#   - ``$default_branches`` = [global, default-branch]; these edges are visible only up to
#     ``$default_time``, which is the queried branch's fork time (``branched_from``) — so
#     default-branch edges created after the fork are excluded. ``$default_time`` is ``$at``
#     when querying the default branch itself, collapsing the two clauses to one.
# (The global branch is in both sets, so global edges are visible up to ``$at`` via the first.)
_BRANCH_VISIBLE = """(
    ({rv}.branch IN $at_branches AND {rv}.from <= $at AND ({rv}.to IS NULL OR {rv}.to >= $at))
    OR
    ({rv}.branch IN $default_branches AND {rv}.from <= $default_time AND ({rv}.to IS NULL OR {rv}.to >= $default_time))
)"""

_EDGE_ACTIVE_PREDICATE = (
    _BRANCH_VISIBLE
    + """
AND {rv}.status = "active" """
)

# ----------------
# Resolve the active Node for a UUID. A kind/namespace/inheritance migration can leave
# several Node vertices sharing one UUID, so for each candidate vertex we take its latest
# IS_PART_OF edge visible on the branch at this time (most-specific branch, then most recent)
# WITHOUT pre-filtering on status, and only then keep the vertex if that latest edge is
# "active". A node deleted on a higher-priority branch therefore wins over a stale "active"
# edge on a lower branch. There should be at most one active Node per UUID per branch; the
# trailing LIMIT 1 is defensive.
# ----------------
_SOURCE_MATCH = """
MATCH (source:Node {uuid: $source_id})
CALL (source) {
    MATCH (source)-[r:IS_PART_OF]->(:Root)
    WHERE %(visible_r)s
    RETURN r AS part_of
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH source, part_of
WHERE part_of.status = "active"
WITH source
LIMIT 1
""" % {"visible_r": _BRANCH_VISIBLE.format(rv="r")}

_TARGET_BY_ID_MATCH = """
MATCH (target:Node {uuid: $target_id})
CALL (target) {
    MATCH (target)-[r:IS_PART_OF]->(:Root)
    WHERE %(visible_r)s
    RETURN r AS part_of
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH source, target, part_of
WHERE part_of.status = "active"
WITH source, target
LIMIT 1
""" % {"visible_r": _BRANCH_VISIBLE.format(rv="r")}

# Same active-Node resolution for a BFS anchor (the source on a forward expansion, the
# destination on a backward one), so the search expands from the anchor's active version.
_SEED_ANCHOR_MATCH = """
MATCH (anchor:Node {uuid: $anchor_id})
CALL (anchor) {
    MATCH (anchor)-[r:IS_PART_OF]->(:Root)
    WHERE %(visible_r)s
    RETURN r AS part_of
    ORDER BY r.branch_level DESC, r.from DESC
    LIMIT 1
}
WITH anchor, part_of
WHERE part_of.status = "active"
WITH anchor
LIMIT 1
""" % {"visible_r": _BRANCH_VISIBLE.format(rv="r")}

_HOP_TUPLE_PREDICATE = """[{start_var}.kind, {rel_var}.name, {end_var}.kind] IN ${hop_tuple_param}"""

_DELETION_SHADOW_PREDICATE = """
NOT EXISTS {{ ({from_var})-[{del_var}:IS_RELATED {{status: "deleted", branch: $user_branch}}]-({to_var})
WHERE {del_var}.from > {edge_var}.from
AND {del_var}.from <= $at
AND ({del_var}.to IS NULL OR {del_var}.to >= $at) }}
"""

_REACHABLE_TARGETS_ENVELOPE = """
%(source_match)s
CALL (source) {
%(phase_one_inner)s
}
WITH source, target
ORDER BY target.kind ASC, target.uuid ASC
LIMIT $max_targets
RETURN collect(target.uuid) AS terminal_uuids
"""

_REACHABLE_PATHS_ENVELOPE = """
%(source_match)s
WITH source, $terminal_uuids AS terminal_uuids
CALL (source, terminal_uuids) {
%(phase_two_inner)s
}
ORDER BY depth ASC, hops[-1].kind ASC, hops[-1].uuid ASC
LIMIT $max_paths
RETURN start_node_uuid, start_node_kind, hops, depth
"""

# By-id bidirectional ("meet-in-the-middle") search. Reaching a single deep target with a
# ``SHORTEST k`` quantified-path-pattern forces the engine to enumerate an exponential
# number of path-steps (cost ~ fan-out ^ depth). Instead, expand a node-bounded BFS
# frontier of depth ceil(max_depth/2) inward from each anchor (cost ~ fan-out ^ (depth/2),
# bounded by graph size, not path count), intersect the frontiers to find candidate middle
# nodes, then reconstruct full paths through that small middle set with exact-length joins.
# The whole BFS from one anchor runs in a single query (``render_bfs``): the active-anchor
# resolution followed by one ``CALL`` subquery per hop, each expanding the previous frontier
# and a carried ``visited`` list deduping globally so a node is recorded at its first-seen
# (shortest) depth. ``$anchor_id`` is the source uuid on a forward expansion, the destination
# uuid on a backward one; it is the uuid excluded from the first hop so the search never
# bounces back onto its anchor.
_BFS_EDGES = "-[ri:IS_RELATED]-(rel:Relationship)-[ro:IS_RELATED]-(b:Node)"

_BFS_HOP_TRIPLE_PREDICATE = "[{from_var}.kind, rel.name, b.kind] IN $hop_triples"

# Hop 1: expand the active anchor (excluding the anchor uuid so we never bounce back), seed
# ``visited``. ``%(where)s`` is the assembled WHERE for this hop.
_BFS_SEED_HOP = """CALL (anchor) {
    MATCH (anchor)%(edges)s
    WHERE %(where)s
    RETURN collect(DISTINCT b.uuid) AS h1
}
WITH h1, [$anchor_id] + h1 AS visited"""

# Hop N>=2: expand the previous frontier ``%(prev)s``, dedup against ``visited``, then carry
# every frontier so far (``%(carried)s`` includes ``%(hop)s``) plus the grown ``visited``.
_BFS_HOP = """CALL (%(prev)s, visited) {
    UNWIND %(prev)s AS fid
    MATCH (a:Node {uuid: fid})%(edges)s
    WHERE %(where)s
    RETURN collect(DISTINCT b.uuid) AS %(hop)s
}
WITH %(carried)s, visited + %(hop)s AS visited"""

# ``_CANONICAL_JOIN`` reconstructs every shortest path of length ``left_len + right_len``
# whose canonical split node sits at forward-distance ``left_len`` and backward-distance
# ``right_len``. Both halves traverse in source→target order (forward ``$legal_triples``);
# the middle is pinned to ``$tier_middles`` (nodes at exactly those bidirectional
# distances). Source and destination are both resolved to their active same-UUID vertex
# (so a migrated node anchors on its active version, not a stale duplicate).
#
# No loop-prevention predicate is needed: an exact-``left_len``-hop path to a node whose
# global forward distance is ``left_len`` is necessarily a simple geodesic (a cycle would
# imply a shorter path, contradicting the distance), so the left half's intermediates
# occupy forward-distances ``1..left_len-1``, the right half's ``left_len+1..depth-1``, and
# the shared middle sits at ``left_len`` — disjoint ranges, no node can repeat.
#
# The ``ORDER BY`` (depth, then the ordered relationship:uuid sequence) matches the caller's
# ascending-depth tier loop: processing tiers in depth order and ordering within a tier by
# this total-order key yields a deterministic prefix of a fixed global order, so the result
# is reproducible and raising ``max_paths`` only appends paths.
_CANONICAL_JOIN = """
%(source_match)s%(target_match)s
WITH source, target
MATCH lpath = (source) %(left_unit)s{%(left_len)d} (mid:Node)
WHERE mid.uuid IN $tier_middles
MATCH rpath = (mid) %(right_unit)s{%(right_len)d} (target)
WITH source, lpath, rpath
WITH
    source.uuid AS start_node_uuid,
    source.kind AS start_node_kind,
    %(depth)d AS depth,
    [i IN range(0, %(left_last)d) | {
        relationship_identifier: nodes(lpath)[i * 2 + 1].name,
        uuid: nodes(lpath)[i * 2 + 2].uuid,
        kind: nodes(lpath)[i * 2 + 2].kind
    }] + [i IN range(0, %(right_last)d) | {
        relationship_identifier: nodes(rpath)[i * 2 + 1].name,
        uuid: nodes(rpath)[i * 2 + 2].uuid,
        kind: nodes(rpath)[i * 2 + 2].kind
    }] AS hops
ORDER BY depth ASC, reduce(ordering_key = "", h IN hops | ordering_key + h.relationship_identifier + ">" + h.uuid) ASC
LIMIT $tier_limit
RETURN start_node_uuid, start_node_kind, hops, depth
"""

# ``_DIRECT_JOIN`` is the ``left_len == 0`` case (a depth-1 path: source and target are
# adjacent, so the middle is the source itself and there is no left half).
_DIRECT_JOIN = """
%(source_match)s%(target_match)s
WITH source, target
MATCH rpath = (source) %(right_unit)s{%(right_len)d} (target)
WITH source, rpath
WITH
    source.uuid AS start_node_uuid,
    source.kind AS start_node_kind,
    %(depth)d AS depth,
    [i IN range(0, %(right_last)d) | {
        relationship_identifier: nodes(rpath)[i * 2 + 1].name,
        uuid: nodes(rpath)[i * 2 + 2].uuid,
        kind: nodes(rpath)[i * 2 + 2].kind
    }] AS hops
ORDER BY depth ASC, reduce(ordering_key = "", h IN hops | ordering_key + h.relationship_identifier + ">" + h.uuid) ASC
LIMIT $tier_limit
RETURN start_node_uuid, start_node_kind, hops, depth
"""


def _reachable_targets_text(*, phase_one_inner: str) -> str:
    return _REACHABLE_TARGETS_ENVELOPE % {"source_match": _SOURCE_MATCH, "phase_one_inner": phase_one_inner}


def _reachable_paths_text(*, phase_two_inner: str) -> str:
    return _REACHABLE_PATHS_ENVELOPE % {"source_match": _SOURCE_MATCH, "phase_two_inner": phase_two_inner}


class GraphTraversalCypherRenderer:
    """Renders a ``Plan`` into Cypher.

    - ``render_bfs()`` / ``render_canonical_join()`` handle ``TerminalById`` as a
      bidirectional search: the caller expands a BFS frontier inward from each anchor
      and then joins the two halves through the discovered middle nodes.
    - ``render_reachable_targets()`` / ``render_paths_to_targets()`` handle
      ``TerminalByKinds`` as two separate queries so a caller can discover the
      terminal set once and then enumerate paths to it depth-by-depth.
    """

    def __init__(self, *, branch: Branch, default_branch_name: str) -> None:
        self._is_user_branch = not branch.is_default
        self._user_branch_name = branch.name
        self._branched_from = branch.branched_from
        # ``$at_branches``: edges on the queried branch (or global) are visible at ``$at``.
        # ``$default_branches``: edges on the default branch (or global) are visible at
        # ``$default_time`` — the branch's fork time.
        self._at_branches: list[str] = [GLOBAL_BRANCH_NAME, branch.name]
        self._default_branches: list[str] = [GLOBAL_BRANCH_NAME, default_branch_name]

    def _branch_params(self, *, at: Timestamp) -> dict[str, Any]:
        """Branch/time params shared by every edge-visibility predicate."""
        if self._is_user_branch and self._branched_from and at > Timestamp(self._branched_from):
            default_time = self._branched_from
        else:
            default_time = at.to_string()
        params: dict[str, Any] = {
            "at": at.to_string(),
            "at_branches": self._at_branches,
            "default_branches": self._default_branches,
            "default_time": default_time,
        }
        if self._is_user_branch:
            params["user_branch"] = self._user_branch_name
        return params

    def _validate(self, *, plan: Plan, max_targets: int | None = None, max_paths: int | None = None) -> None:
        """Reject out-of-range caps and empty plans before rendering.

        Raises:
            ValueError: when a supplied cap is out of range or the plan is empty.

        """
        if max_targets is not None and not _MAX_TARGETS_MINIMUM <= max_targets <= _MAX_TARGETS_MAXIMUM:
            raise ValueError(
                f"max_targets must be in [{_MAX_TARGETS_MINIMUM}, {_MAX_TARGETS_MAXIMUM}], got {max_targets}"
            )
        if max_paths is not None and not _MAX_PATHS_MINIMUM <= max_paths <= _MAX_PATHS_MAXIMUM:
            raise ValueError(f"max_paths must be in [{_MAX_PATHS_MINIMUM}, {_MAX_PATHS_MAXIMUM}], got {max_paths}")
        if plan.is_empty:
            raise ValueError("plan has no adjacency")

    def _base_params(self, *, source_id: str, at: Timestamp) -> dict[str, Any]:
        """Params common to every rendered query: source anchor plus branch/time scope."""
        return {"source_id": source_id, **self._branch_params(at=at)}

    def _phase_one_inner(self, *, plan: Plan, depth_renders: list[_DepthRenderData]) -> str:
        terminal_label_union = "|".join(sorted(_terminal_kinds_for_plan(plan)))
        return "\n  UNION\n".join(
            self._render_phase_one_for_depth(dr, terminal_label_union=terminal_label_union) for dr in depth_renders
        )

    def _phase_two_inner(self, *, plan: Plan, depth_renders: list[_DepthRenderData]) -> str:
        terminal_label_union = "|".join(sorted(_terminal_kinds_for_plan(plan)))
        return "\n  UNION ALL\n".join(
            self._render_phase_two_for_depth(dr, terminal_label_union=terminal_label_union) for dr in depth_renders
        )

    def render_reachable_targets(
        self, *, plan: Plan, source_id: str, at: Timestamp | None, max_targets: int
    ) -> RenderedCypher:
        """Render Phase 1 for ``TerminalByKinds``: discover up to ``max_targets`` terminal uuids.

        Returns a query whose single column ``terminal_uuids`` is the ordered,
        capped list of discovered terminal-node uuids.

        Raises:
            ValueError: when ``plan`` is empty, ``max_targets`` is out of range,
                or no feasible fixed-depth query reaches the terminal.

        """
        self._validate(plan=plan, max_targets=max_targets)

        at = at if at is not None else Timestamp()
        depth_renders = self._feasible_for_depths(plan=plan, terminal_kinds=_terminal_kinds_for_plan(plan), depths=None)
        text = _reachable_targets_text(phase_one_inner=self._phase_one_inner(plan=plan, depth_renders=depth_renders))
        params: dict[str, Any] = {
            **self._base_params(source_id=source_id, at=at),
            "max_targets": max_targets,
            **self._hop_tuple_params(depth_renders),
        }
        return RenderedCypher(text=text, params=params, return_labels=_TARGETS_RETURN_LABELS)

    def render_paths_to_targets(
        self,
        *,
        plan: Plan,
        source_id: str,
        at: Timestamp | None,
        terminal_uuids: list[str],
        max_paths: int,
        depths: Iterable[int] | None = None,
    ) -> RenderedCypher:
        """Render Phase 2 for ``TerminalByKinds``: enumerate paths to ``terminal_uuids``.

        ``terminal_uuids`` is bound as a query parameter (the discovered set from
        ``render_reachable_targets``). ``depths`` restricts the rendered
        fixed-depth queries; ``None`` renders every feasible depth.

        Raises:
            ValueError: when ``plan`` is empty, ``max_paths`` is out of range,
                or no feasible fixed-depth query survives the ``depths`` restriction.

        """
        self._validate(plan=plan, max_paths=max_paths)

        at = at if at is not None else Timestamp()
        depth_renders = self._feasible_for_depths(
            plan=plan, terminal_kinds=_terminal_kinds_for_plan(plan), depths=depths
        )
        text = _reachable_paths_text(phase_two_inner=self._phase_two_inner(plan=plan, depth_renders=depth_renders))
        params: dict[str, Any] = {
            **self._base_params(source_id=source_id, at=at),
            "terminal_uuids": list(terminal_uuids),
            "max_paths": max_paths,
            **self._hop_tuple_params(depth_renders),
        }
        return RenderedCypher(text=text, params=params, return_labels=_RETURN_LABELS)

    def render_bfs(
        self,
        *,
        plan: Plan,
        source_id: str,
        target_id: str,
        direction: Literal["forward", "backward"],
        max_hops: int,
        at: Timestamp | None,
    ) -> RenderedCypher:
        """Render the whole BFS from one anchor as a single query.

        Resolves the anchor to its active same-UUID vertex, then chains one ``CALL``
        subquery per hop (1..``max_hops``): each expands the previous frontier by one legal
        edge and a carried ``visited`` list dedupes globally, so a node is recorded only at
        its first-seen (shortest) depth. ``forward`` walks from the source with
        ``$legal_triples``; ``backward`` walks from the destination with the reversed
        triples. Returns a single ``frontiers`` column: a list whose ``i``-th element is the
        list of node uuids first reached at depth ``i + 1``.

        Raises:
            ValueError: when ``plan`` is empty, ``direction`` is unknown, or ``max_hops < 1``.

        """
        self._validate(plan=plan)
        if max_hops < 1:
            raise ValueError(f"max_hops must be >= 1, got {max_hops}")
        at = at if at is not None else Timestamp()
        if direction == "forward":
            triples = _legal_triples(plan)
            anchor_id = source_id
        elif direction == "backward":
            triples = _legal_triples_reversed(plan)
            anchor_id = target_id
        else:
            raise ValueError(f"direction must be 'forward' or 'backward', got {direction!r}")

        def hop_where(from_var: str, dedup: str) -> str:
            preds = [
                _EDGE_ACTIVE_PREDICATE.format(rv="ri"),
                _EDGE_ACTIVE_PREDICATE.format(rv="ro"),
                _BFS_HOP_TRIPLE_PREDICATE.format(from_var=from_var),
                dedup,
            ]
            if self._is_user_branch:
                preds.append(
                    _DELETION_SHADOW_PREDICATE.format(from_var=from_var, to_var="rel", edge_var="ri", del_var="del_a")
                )
                preds.append(
                    _DELETION_SHADOW_PREDICATE.format(from_var="rel", to_var="b", edge_var="ro", del_var="del_b")
                )
            return " AND ".join(preds)

        parts = [
            _SEED_ANCHOR_MATCH,
            _BFS_SEED_HOP % {"edges": _BFS_EDGES, "where": hop_where("anchor", "b.uuid <> $anchor_id")},
        ]
        carried = ["h1"]
        for hop in range(2, max_hops + 1):
            hop_name = f"h{hop}"
            carried.append(hop_name)
            parts.append(
                _BFS_HOP
                % {
                    "prev": f"h{hop - 1}",
                    "edges": _BFS_EDGES,
                    "where": hop_where("a", "NOT b.uuid IN visited"),
                    "hop": hop_name,
                    "carried": ", ".join(carried),
                }
            )
        parts.append("RETURN [%s] AS frontiers" % ", ".join(carried))

        text = "\n".join(parts)
        params: dict[str, Any] = {**self._branch_params(at=at), "hop_triples": triples, "anchor_id": anchor_id}
        return RenderedCypher(text=text, params=params, return_labels=("frontiers",))

    def render_canonical_join(
        self,
        *,
        plan: Plan,
        source_id: str,
        target_id: str,
        left_len: int,
        right_len: int,
        tier_middles: list[str],
        tier_limit: int,
        at: Timestamp | None,
    ) -> RenderedCypher:
        """Render the path-reconstruction join for one depth tier of the by-id search.

        Reconstructs every shortest path of length ``left_len + right_len`` whose
        canonical split node (at forward-distance ``left_len``, backward-distance
        ``right_len``) is in ``tier_middles``. ``left_len == 0`` is the depth-1 case
        (source and destination are adjacent): the middle is the source itself and only
        the right half is emitted.

        Raises:
            ValueError: when ``plan`` is empty, ``max_paths`` (``tier_limit``) is out of
                range, or ``right_len < 1``.

        """
        self._validate(plan=plan, max_paths=tier_limit)
        if right_len < 1:
            raise ValueError(f"right_len must be >= 1, got {right_len}")
        if left_len < 0:
            raise ValueError(f"left_len must be >= 0, got {left_len}")

        at = at if at is not None else Timestamp()
        right_unit = self._join_unit(_QppVars(start="c", edge_in="si", rel="srel", edge_out="so", end="d"))
        depth = left_len + right_len
        params: dict[str, Any] = {
            **self._base_params(source_id=source_id, at=at),
            "target_id": target_id,
            "legal_triples": _legal_triples(plan),
            "tier_limit": tier_limit,
        }
        if left_len == 0:
            text = _DIRECT_JOIN % {
                "source_match": _SOURCE_MATCH,
                "target_match": _TARGET_BY_ID_MATCH,
                "right_unit": right_unit,
                "right_len": right_len,
                "right_last": right_len - 1,
                "depth": depth,
            }
        else:
            left_unit = self._join_unit(_QppVars(start="a", edge_in="ri", rel="relx", edge_out="ro", end="b"))
            text = _CANONICAL_JOIN % {
                "source_match": _SOURCE_MATCH,
                "target_match": _TARGET_BY_ID_MATCH,
                "left_unit": left_unit,
                "right_unit": right_unit,
                "left_len": left_len,
                "right_len": right_len,
                "left_last": left_len - 1,
                "right_last": right_len - 1,
                "depth": depth,
            }
            params["tier_middles"] = list(tier_middles)
        return RenderedCypher(text=text, params=params, return_labels=_RETURN_LABELS)

    def _join_unit(self, qpp: _QppVars) -> str:
        """One forward quantified-path-pattern hop for the canonical join."""
        preds = [
            _EDGE_ACTIVE_PREDICATE.format(rv=qpp.edge_in),
            _EDGE_ACTIVE_PREDICATE.format(rv=qpp.edge_out),
            f"[{qpp.start}.kind, {qpp.rel}.name, {qpp.end}.kind] IN $legal_triples",
            f"{qpp.end}.uuid <> $source_id",
        ]
        if self._is_user_branch:
            preds.append(
                _DELETION_SHADOW_PREDICATE.format(
                    from_var=qpp.start, to_var=qpp.rel, edge_var=qpp.edge_in, del_var=f"del_{qpp.edge_in}"
                )
            )
            preds.append(
                _DELETION_SHADOW_PREDICATE.format(
                    from_var=qpp.rel, to_var=qpp.end, edge_var=qpp.edge_out, del_var=f"del_{qpp.edge_out}"
                )
            )
        return (
            f"( ({qpp.start})-[{qpp.edge_in}:IS_RELATED]-({qpp.rel}:Relationship)"
            f"-[{qpp.edge_out}:IS_RELATED]-({qpp.end}:Node)\n    WHERE {' AND '.join(preds)} )"
        )

    def _feasible_for_depths(
        self, *, plan: Plan, terminal_kinds: frozenset[str], depths: Iterable[int] | None
    ) -> list[_DepthRenderData]:
        depth_renders = self._build_depth_renders(plan=plan, terminal_kinds=terminal_kinds)
        if depths is not None:
            requested_depths = set(depths)
            depth_renders = [dr for dr in depth_renders if dr.depth in requested_depths]
        if not depth_renders:
            # Defensive: the planner's reverse-BFS pruning guarantees that any
            # non-empty plan has at least one depth reaching the terminal
            raise ValueError("plan has adjacency but no feasible fixed-depth query within max_depth")
        return depth_renders

    def _hop_tuple_params(self, depth_renders: list[_DepthRenderData]) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for depth_render in depth_renders:
            for hop_idx, hop_tuples in enumerate(depth_render.tuples_per_hop, start=1):
                params[depth_render.hop_tuple_param(hop_idx)] = [list(t) for t in hop_tuples]
        return params

    def feasible_depths(self, *, plan: Plan) -> list[int]:
        """Ascending depths for which ``plan`` has a renderable fixed-depth query.

        Empty for an empty plan. Callers iterating depth-by-depth should loop
        over this list rather than ``range(1, plan.max_depth + 1)`` so that
        per-depth ``render()`` calls never hit the no-feasible-depth error.
        """
        if plan.is_empty:
            return []
        terminal_kinds = _terminal_kinds_for_plan(plan)
        return [dr.depth for dr in self._build_depth_renders(plan=plan, terminal_kinds=terminal_kinds)]

    def _build_depth_renders(self, *, plan: Plan, terminal_kinds: frozenset[str]) -> list[_DepthRenderData]:
        """Compute the renderable per-depth structure once. Both phases consume the same data."""
        depth_renders: list[_DepthRenderData] = []
        for depth in range(1, plan.max_depth + 1):
            per_step = self._per_step_kinds_for_depth(plan=plan, depth=depth)
            tuples_per_hop = self._hop_tuples_for_depth(
                plan=plan, terminal_kinds=terminal_kinds, depth=depth, per_step_kinds=per_step
            )
            if tuples_per_hop is None:
                continue
            depth_renders.append(_DepthRenderData(depth=depth, per_step_kinds=per_step, tuples_per_hop=tuples_per_hop))
        return depth_renders

    def _per_step_kinds_for_depth(self, *, plan: Plan, depth: int) -> list[list[str]]:
        """Per-intermediate-position kind sets.

        Always non-empty for a non-empty plan: the terminal kind has
        ``min_depth_to_terminal == 0``, so ``get_kinds_within_hops_of_terminal``
        returns at least the terminal for any ``max_hops >= 1``.
        """
        return [plan.get_kinds_within_hops_of_terminal(max_hops=depth - k) for k in range(1, depth)]

    def _hop_tuples_for_depth(
        self,
        *,
        plan: Plan,
        terminal_kinds: frozenset[str],
        depth: int,
        per_step_kinds: list[list[str]],
    ) -> list[list[HopTuple]] | None:
        """Per-hop legal ``HopTuple`` lists restricted to the position's allowed kinds.

        Returns ``None`` when any hop has no surviving hop tuples.
        """
        tuples_per_hop: list[list[HopTuple]] = []
        for hop in range(1, depth + 1):
            starts: set[str] = {plan.source_kind} if hop == 1 else set(per_step_kinds[hop - 2])
            ends: frozenset[str] | set[str] = terminal_kinds if hop == depth else set(per_step_kinds[hop - 1])
            hop_tuples: list[HopTuple] = []
            for start in sorted(starts):
                rel_map = plan.get_relationship_map_for_kind(start)
                for rel_name in sorted(rel_map):
                    for end in rel_map[rel_name]:
                        if end in ends:
                            hop_tuples.append(HopTuple(start, rel_name, end))
            if not hop_tuples:
                return None
            tuples_per_hop.append(hop_tuples)
        return tuples_per_hop

    def _render_phase_one_for_depth(self, depth_render: _DepthRenderData, *, terminal_label_union: str) -> str:
        """Phase 1 per-depth query: chained DISTINCT-capped CALLs returning ``target``.

        Each hop is a separate ``CALL (var) { ... RETURN DISTINCT bN }``
        subquery. Between hops, a ``WITH … ORDER BY bN.kind, bN.uuid LIMIT $max_targets``
        clause caps intermediate cardinality so the chain can't multiply out.

        Example shape for depth=3::

            CALL (source) {
              MATCH (source)-[ra]-(rel:Relationship)-[rb]-(b1:K1|K2|...)
              WHERE <edge active> AND <hop1 triple> AND b1.uuid <> $source_id AND <deletion shadow>
              RETURN DISTINCT b1
            }
            WITH source, b1
            ORDER BY b1.kind ASC, b1.uuid ASC
            LIMIT $max_targets
            CALL (b1) {
              MATCH (b1)-[ra]-(rel:Relationship)-[rb]-(b2:K1|...)
              WHERE <edge active> AND <hop2 triple> AND b2.uuid <> $source_id AND <deletion shadow>
              RETURN DISTINCT b2
            }
            WITH source, b1, b2
            ORDER BY b2.kind ASC, b2.uuid ASC
            LIMIT $max_targets
            CALL (b2) {
              MATCH (b2)-[ra]-(rel:Relationship)-[rb]-(target:TerminalKinds)
              WHERE <edge active> AND <hop3 triple> AND target.uuid <> $source_id AND <deletion shadow>
              RETURN DISTINCT target
            }
            RETURN target
        """
        depth = depth_render.depth
        parts: list[str] = []
        accumulated: list[str] = ["source"]
        for hop in range(1, depth + 1):
            from_var = "source" if hop == 1 else f"b{hop - 1}"
            to_var = "target" if hop == depth else f"b{hop}"
            to_pattern = self._end_node_pattern(
                depth_render=depth_render, hop=hop, to_var=to_var, terminal_label_union=terminal_label_union
            )
            r_in, rel_var, r_out = "ra", "rel", "rb"
            # Phase 1 source-excludes every hop's destination, including the
            # terminal — so $source_id never enters terminal_uuids.
            preds = self._hop_predicates(
                depth_render=depth_render,
                hop=hop,
                from_var=from_var,
                rel_var=rel_var,
                to_var=to_var,
                r_in=r_in,
                r_out=r_out,
                source_exclude_on_target=True,
                intermediate_exclude_target=False,
            )
            parts.append(
                """
CALL (%(from_var)s) {
    MATCH (%(from_var)s)-[%(r_in)s:IS_RELATED]-(%(rel_var)s:Relationship)-[%(r_out)s:IS_RELATED]-%(to_pattern)s
    WHERE %(preds)s
    RETURN DISTINCT %(to_var)s
}"""
                % {
                    "from_var": from_var,
                    "r_in": r_in,
                    "rel_var": rel_var,
                    "r_out": r_out,
                    "to_pattern": to_pattern,
                    "to_var": to_var,
                    "preds": " AND ".join(preds),
                }
            )
            accumulated.append(to_var)
            if hop < depth:
                parts.append(
                    """
WITH %(accumulated)s
ORDER BY %(to_var)s.kind ASC, %(to_var)s.uuid ASC
LIMIT $max_targets"""
                    % {"accumulated": ", ".join(accumulated), "to_var": to_var}
                )
        parts.append("    RETURN target")
        return "\n".join(parts)

    def _render_phase_two_for_depth(self, depth_render: _DepthRenderData, *, terminal_label_union: str) -> str:
        """Phase 2 per-depth query: fixed-length ``MATCH`` constrained to ``target.uuid IN terminal_uuids``.

        For depth-``d`` paths, builds a single ``MATCH`` with ``2d`` IS_RELATED
        edges and ``d`` Relationship vertices. Each hop carries the per-hop
        triple predicate, edge active/branch filters, deletion-shadow checks on
        user branches, and intermediate distinctness checks. After all hops,
        appends ``d - 2`` predicates forbidding any later intermediate uuid
        from matching an earlier one to prevent loops.

        Example shape for depth=3::

            MATCH (source)-[r1_s]-(rel1:Relationship)-[r1_e]-(b1:K1|...)
                          -[r2_s]-(rel2:Relationship)-[r2_e]-(b2:K1|...)
                          -[r3_s]-(rel3:Relationship)-[r3_e]-(target:TerminalKinds)
            WHERE target.uuid IN terminal_uuids
              AND <edge active for r1_s, r1_e>
              AND <hop1 triple>
              AND b1.uuid <> $source_id AND b1 <> target
              AND <deletion shadow per hop, on user branches>
              AND <edge active for r2_s, r2_e> AND <hop2 triple>
              AND b2.uuid <> $source_id AND b2 <> target
              AND <edge active for r3_s, r3_e> AND <hop3 triple>
              AND NOT b2.uuid IN [b1.uuid]
            RETURN source.uuid AS start_node_uuid, source.kind AS start_node_kind,
                   [{rel_id: rel1.name, uuid: b1.uuid, kind: b1.kind},
                    {rel_id: rel2.name, uuid: b2.uuid, kind: b2.kind},
                    {rel_id: rel3.name, uuid: target.uuid, kind: target.kind}] AS hops,
                   3 AS depth

        At depth=4 the trailing predicates expand to::

              AND NOT b2.uuid IN [b1.uuid]
              AND NOT b3.uuid IN [b1.uuid, b2.uuid]
        """
        depth = depth_render.depth
        path_segs: list[str] = ["(source)"]
        preds: list[str] = ["target.uuid IN terminal_uuids"]
        for hop in range(1, depth + 1):
            r_s, rel_var, r_e = f"r{hop}_s", f"rel{hop}", f"r{hop}_e"
            from_var = "source" if hop == 1 else f"b{hop - 1}"
            to_var = "target" if hop == depth else f"b{hop}"
            to_pattern = self._end_node_pattern(
                depth_render=depth_render, hop=hop, to_var=to_var, terminal_label_union=terminal_label_union
            )
            path_segs.append(f"-[{r_s}:IS_RELATED]-({rel_var}:Relationship)-[{r_e}:IS_RELATED]-{to_pattern}")
            # Phase 2 source-excludes intermediates only b/c target is
            # constrained by ``target.uuid IN terminal_uuids`` and Phase 1
            # filtered $source_id out of terminal_uuids
            preds.extend(
                self._hop_predicates(
                    depth_render=depth_render,
                    hop=hop,
                    from_var=from_var,
                    rel_var=rel_var,
                    to_var=to_var,
                    r_in=r_s,
                    r_out=r_e,
                    source_exclude_on_target=False,
                    intermediate_exclude_target=True,
                )
            )

        # Prevent loops that return to an intermediate object
        for hop in range(2, depth):
            earlier = ", ".join(f"b{h}.uuid" for h in range(1, hop))
            preds.append(f"NOT b{hop}.uuid IN [{earlier}]")

        hop_entries: list[str] = []
        for hop in range(1, depth + 1):
            rel_var = f"rel{hop}"
            node_var = "target" if hop == depth else f"b{hop}"
            hop_entries.append(
                f"{{relationship_identifier: {rel_var}.name, uuid: {node_var}.uuid, kind: {node_var}.kind}}"
            )
        hops_list = ", ".join(hop_entries)

        return """
MATCH %(path)s
WHERE %(where)s
RETURN
    source.uuid AS start_node_uuid,
    source.kind AS start_node_kind,
    [%(hops_list)s] AS hops, %(depth)s AS depth""" % {
            "path": "".join(path_segs),
            "where": " AND ".join(preds),
            "hops_list": hops_list,
            "depth": depth,
        }

    def _end_node_pattern(
        self, *, depth_render: _DepthRenderData, hop: int, to_var: str, terminal_label_union: str
    ) -> str:
        """Return the ``(var:Labels)`` pattern fragment for the destination node at ``hop``."""
        if hop < depth_render.depth:
            return f"({to_var}:{'|'.join(depth_render.per_step_kinds[hop - 1])})"
        return f"(target:{terminal_label_union})"

    def _hop_predicates(
        self,
        *,
        depth_render: _DepthRenderData,
        hop: int,
        from_var: str,
        rel_var: str,
        to_var: str,
        r_in: str,
        r_out: str,
        source_exclude_on_target: bool,
        intermediate_exclude_target: bool,
    ) -> list[str]:
        """Build the WHERE predicates for one hop's MATCH fragment.

        Always emits: edge active/branch filters for ``r_in``/``r_out``, the
        per-hop triple constraint, source-exclude on intermediate destinations,
        and (on user branches) two deletion-shadow ``NOT EXISTS`` subqueries.

        ``source_exclude_on_target=True`` adds ``target.uuid <> $source_id`` on
        the final hop — used by Phase 1 so $source_id can't sneak into the
        discovered terminal set. Phase 2 leaves it off since ``target.uuid IN
        terminal_uuids`` already filtered.

        ``intermediate_exclude_target=True`` adds ``bN <> target`` on each
        intermediate hop — used by Phase 2 to prevent an intermediate vertex
        from coinciding with the anchored target.
        """
        is_intermediate = hop < depth_render.depth
        preds: list[str] = [_EDGE_ACTIVE_PREDICATE.format(rv=rv) for rv in (r_in, r_out)]
        preds.append(
            _HOP_TUPLE_PREDICATE.format(
                start_var=from_var,
                rel_var=rel_var,
                end_var=to_var,
                hop_tuple_param=depth_render.hop_tuple_param(hop),
            )
        )
        if is_intermediate or source_exclude_on_target:
            preds.append(f"{to_var}.uuid <> $source_id")
        if is_intermediate and intermediate_exclude_target:
            preds.append(f"{to_var} <> target")
        if self._is_user_branch:
            preds.append(
                _DELETION_SHADOW_PREDICATE.format(from_var=from_var, to_var=rel_var, edge_var=r_in, del_var="del_a")
            )
            preds.append(
                _DELETION_SHADOW_PREDICATE.format(from_var=rel_var, to_var=to_var, edge_var=r_out, del_var="del_b")
            )
        return preds

"""Cypher renderer for the graph-traversal planner.

Two terminal predicates are served by separate entry points:

- ``TerminalById`` (``render_shortest_path_by_id``): both endpoints are resolved
  to their branch/time-correct active ``Node`` rows, then a single ``SHORTEST k``
  quantified-path-pattern search between the two bound nodes returns up to
  ``$max_paths`` paths to the target, shortest first.

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

- ``$valid_branches``: ``[default, global]`` on the default branch;
  ``[default, global, user]`` on a user branch.
- On a user branch each hop in both phases gets two ``NOT EXISTS``
  deletion-shadow checks (one for each side of the ``Relationship`` vertex)
  and the query binds ``$user_branch``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

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


_SOURCE_MATCH = """
// ----------------
// get the latest Node with this UUID in case it had its kind/inheritance migrated
// and multiple Nodes with the same UUID exist, assumes the Node is active
// ----------------
MATCH (source:Node {uuid: $source_id})-[source_active:IS_PART_OF]->(:Root)
WHERE source_active.branch IN $valid_branches AND source_active.status = "active"
  AND source_active.from <= $at AND (source_active.to IS NULL OR source_active.to >= $at)
WITH source
ORDER BY source_active.branch_level DESC, source_active.from DESC
LIMIT 1
"""

_TARGET_BY_ID_MATCH = """
// ----------------
// get the latest Node with this UUID in case it had its kind/inheritance migrated
// and multiple Nodes with the same UUID exist, assumes the Node is active
// ----------------
MATCH (target:Node {uuid: $target_id})-[target_active:IS_PART_OF]->(:Root)
WHERE target_active.branch IN $valid_branches AND target_active.status = "active"
  AND target_active.from <= $at AND (target_active.to IS NULL OR target_active.to >= $at)
WITH source, target
ORDER BY target_active.branch_level DESC, target_active.from DESC
LIMIT 1
"""

_EDGE_ACTIVE_PREDICATE = """
{rv}.branch IN $valid_branches
AND {rv}.status = "active"
AND {rv}.from <= $at
AND ({rv}.to IS NULL OR {rv}.to >= $at)
"""

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

# By-id k-SHORTEST: resolve both endpoints to their branch/time-correct active Node
# rows, then run a single quantified-path-pattern search for the ``max_paths`` shortest
# paths between the two bound nodes. ``SHORTEST k`` walks Neo4j's frontier in a stable
# traversal order and stops once ``k`` paths are found, so shallow targets return
# without exploring the full ``max_depth`` cone. The outer ``ORDER BY`` gives a stable
# presentation order (depth, then the intermediate relationship:uuid sequence). Binding
# both ``source`` and ``target`` lets the planner anchor both ends.
#
# Determinism note: the result is fully reproducible whenever the number of connecting
# paths is <= ``max_paths`` (no tier is cut). When more paths exist than ``max_paths``,
# which paths fill the final tier is decided by Neo4j's traversal order and is stable for
# unchanged data and a fixed Neo4j version/plan.
_PATH_BY_ID_SHORTEST_ENVELOPE = """
%(source_match)s%(target_match)s
MATCH path = SHORTEST %(k)s (source) %(unit)s (target)
WITH
    source.uuid AS start_node_uuid,
    source.kind AS start_node_kind,
    (size(nodes(path)) - 1) / 2 AS depth,
    [i IN range(0, (size(nodes(path)) - 1) / 2 - 1) | {
        relationship_identifier: nodes(path)[i * 2 + 1].name,
        uuid: nodes(path)[i * 2 + 2].uuid,
        kind: nodes(path)[i * 2 + 2].kind
    }] AS hops
ORDER BY depth ASC, reduce(ordering_key = "", h IN hops | ordering_key + h.relationship_identifier + ">" + h.uuid) ASC
RETURN start_node_uuid, start_node_kind, hops, depth
"""


def _path_by_id_shortest_text(*, unit: str, k: int) -> str:
    return _PATH_BY_ID_SHORTEST_ENVELOPE % {
        "source_match": _SOURCE_MATCH,
        "target_match": _TARGET_BY_ID_MATCH,
        "unit": unit,
        "k": k,
    }


def _reachable_targets_text(*, phase_one_inner: str) -> str:
    return _REACHABLE_TARGETS_ENVELOPE % {"source_match": _SOURCE_MATCH, "phase_one_inner": phase_one_inner}


def _reachable_paths_text(*, phase_two_inner: str) -> str:
    return _REACHABLE_PATHS_ENVELOPE % {"source_match": _SOURCE_MATCH, "phase_two_inner": phase_two_inner}


class GraphTraversalCypherRenderer:
    """Renders a ``Plan`` into Cypher.

    - ``render_shortest_path_by_id()`` handles ``TerminalById``: resolves both
      endpoints to bound nodes and runs a single ``SHORTEST k`` search between them.
    - ``render_reachable_targets()`` / ``render_paths_to_targets()`` handle
      ``TerminalByKinds`` as two separate queries so a caller can discover the
      terminal set once and then enumerate paths to it depth-by-depth.
    """

    def __init__(self, *, branch: Branch, default_branch_name: str) -> None:
        self._is_user_branch = not branch.is_default
        self._user_branch_name = branch.name
        self._valid_branches: list[str] = (
            [default_branch_name, GLOBAL_BRANCH_NAME]
            if branch.is_default
            else [default_branch_name, GLOBAL_BRANCH_NAME, branch.name]
        )

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
        """Params common to every rendered query: source anchor, timestamp, branch scope."""
        params: dict[str, Any] = {
            "source_id": source_id,
            "at": at.to_string(),
            "valid_branches": self._valid_branches,
        }
        if self._is_user_branch:
            params["user_branch"] = self._user_branch_name
        return params

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

    def render_shortest_path_by_id(
        self, *, plan: Plan, source_id: str, at: Timestamp | None, max_paths: int
    ) -> RenderedCypher:
        """Render a ``SHORTEST k`` search for a ``TerminalById`` target.

        Returns up to ``max_paths`` paths to the anchored destination, shortest
        first, with a stable presentation order (depth, then the ordered
        intermediate ``relationship:uuid`` sequence). Fully reproducible when the
        number of connecting paths is at most ``max_paths``; beyond that, which
        paths fill the final tier follows Neo4j's traversal order.

        Raises:
            ValueError: when ``plan`` is empty, ``max_paths`` is out of range, or
                the terminal is not anchored by id.

        """
        self._validate(plan=plan, max_paths=max_paths)
        if not isinstance(plan.terminal_predicate, TerminalById):
            raise ValueError("render_shortest_path_by_id handles TerminalById only")

        at = at if at is not None else Timestamp()
        text = _path_by_id_shortest_text(unit=self._shortest_qpp_unit(max_depth=plan.max_depth), k=max_paths)
        params: dict[str, Any] = {
            **self._base_params(source_id=source_id, at=at),
            "target_id": plan.terminal_predicate.node_id,
            "legal_triples": _legal_triples(plan),
        }
        return RenderedCypher(text=text, params=params, return_labels=_RETURN_LABELS)

    def _shortest_qpp_unit(self, *, max_depth: int) -> str:
        """The repeated quantified-path-pattern unit: one schema hop with its predicates."""
        preds = [
            _EDGE_ACTIVE_PREDICATE.format(rv="ri"),
            _EDGE_ACTIVE_PREDICATE.format(rv="ro"),
            "[a.kind, relx.name, b.kind] IN $legal_triples",
            "b.uuid <> $source_id",
        ]
        if self._is_user_branch:
            preds.append(_DELETION_SHADOW_PREDICATE.format(from_var="a", to_var="relx", edge_var="ri", del_var="del_a"))
            preds.append(_DELETION_SHADOW_PREDICATE.format(from_var="relx", to_var="b", edge_var="ro", del_var="del_b"))
        where = " AND ".join(preds)
        return (
            f"( (a)-[ri:IS_RELATED]-(relx:Relationship)-[ro:IS_RELATED]-(b:Node)\n    WHERE {where} ){{1,{max_depth}}}"
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

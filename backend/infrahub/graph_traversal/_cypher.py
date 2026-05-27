"""Cypher renderer for the graph-traversal planner.

The rendered query is two-phase:

- **Phase 1** (for ``TerminalByKinds`` only — i.e. ``ReachableNodesQuery``):
  per-depth chained ``DISTINCT`` CALLs discover up to ``$max_targets`` distinct
  terminal vertices. Inter-CALL ``ORDER BY kind, uuid LIMIT $max_targets``
  clauses keep the intermediate cardinality bounded.

- **Phase 2** (both ``TerminalByKinds`` and ``TerminalById`` — i.e. ``PathTraversalQuery``):
  per-depth fixed-length ``MATCH`` branches anchored on ``source`` and
  ``target.uuid IN terminal_uuids`` enumerate every path of length
  ``≤ plan.max_depth`` to the discovered/given terminal(s), bounded by
  ``$max_paths``.

``TerminalById`` skips Phase 1; the target is anchored via its uuid and the
``terminal_uuids`` list is the single-element ``[target.uuid]``.

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
    from infrahub.core.branch import Branch


class HopTuple(NamedTuple):
    """A legal ``(start_kind, relationship_identifier, end_kind)`` schema hop."""

    start_kind: str
    relationship_identifier: str
    end_kind: str


_RETURN_LABELS: tuple[str, ...] = ("start_node_uuid", "start_node_kind", "hops", "depth")

_MAX_TARGETS_MINIMUM = 1
_MAX_TARGETS_MAXIMUM = 200

_MAX_PATHS_MINIMUM = 1
_MAX_PATHS_MAXIMUM = 10000


@dataclass(frozen=True, slots=True)
class RenderedCypher:
    text: str
    params: dict[str, Any]
    return_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _DepthBranchData:
    """Pre-computed data for rendering one fixed-depth branch (Phase 1 or Phase 2).

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

_REACHABLE_NODES_ENVELOPE = """
%(source_match)s
CALL (source) {
%(phase_one_inner)s
}
WITH source, target
ORDER BY target.kind ASC, target.uuid ASC
LIMIT $max_targets
WITH source, collect(target.uuid) AS terminal_uuids
CALL (source, terminal_uuids) {
%(phase_two_inner)s
}
ORDER BY depth ASC, hops[-1].kind ASC, hops[-1].uuid ASC
LIMIT $max_paths
RETURN start_node_uuid, start_node_kind, hops, depth
"""

_PATH_TRAVERSAL_ENVELOPE = """
%(source_match)s%(target_match)s
WITH source, [target.uuid] AS terminal_uuids
CALL (source, terminal_uuids) {
%(phase_two_inner)s
}
ORDER BY depth ASC, hops[-1].kind ASC, hops[-1].uuid ASC
LIMIT $max_paths
RETURN start_node_uuid, start_node_kind, hops, depth
"""


class PathTraversalCypherRenderer:
    """Renders a ``Plan`` into a two-phase Cypher query.

    ``render()`` dispatches on ``plan.terminal_predicate`` type:

    - ``TerminalByKinds`` emits Phase 1 (terminal discovery, capped at
      ``$max_targets``) and Phase 2 (path enumeration, capped at ``$max_paths``).
    - ``TerminalById`` anchors the given target, builds
      ``terminal_uuids = [target.uuid]``, runs only Phase 2.

    Raises:
        ValueError: when ``max_targets`` is out of range or
            ``max_paths`` is out of range.

    """

    def __init__(
        self,
        *,
        branch: Branch,
        default_branch_name: str,
        at: Timestamp | None,
        max_targets: int,
        max_paths: int,
    ) -> None:
        if not _MAX_TARGETS_MINIMUM <= max_targets <= _MAX_TARGETS_MAXIMUM:
            raise ValueError(
                f"max_targets must be in [{_MAX_TARGETS_MINIMUM}, {_MAX_TARGETS_MAXIMUM}], got {max_targets}"
            )
        if not _MAX_PATHS_MINIMUM <= max_paths <= _MAX_PATHS_MAXIMUM:
            raise ValueError(f"max_paths must be in [{_MAX_PATHS_MINIMUM}, {_MAX_PATHS_MAXIMUM}], got {max_paths}")

        self._at = at if at is not None else Timestamp()
        self._max_targets = max_targets
        self._max_paths = max_paths

        self._is_user_branch = not branch.is_default
        self._user_branch_name = branch.name
        self._valid_branches: list[str] = (
            [default_branch_name, GLOBAL_BRANCH_NAME]
            if branch.is_default
            else [default_branch_name, GLOBAL_BRANCH_NAME, branch.name]
        )

    def render(self, *, plan: Plan, source_id: str) -> RenderedCypher:
        """Render ``plan`` as a two-phase Cypher query rooted at ``source_id``.

        Raises:
            ValueError: when ``plan`` is empty or no feasible fixed-depth branch
                survives the per-step budget.

        """
        if plan.is_empty:
            raise ValueError("plan has no adjacency")

        terminal_anchored_by_id = isinstance(plan.terminal_predicate, TerminalById)
        terminal_kinds: frozenset[str] = (
            frozenset({plan.terminal_predicate.kind})
            if isinstance(plan.terminal_predicate, TerminalById)
            else plan.terminal_predicate.kinds
        )
        terminal_label_union = "|".join(sorted(terminal_kinds))

        feasible = self._build_feasible_branches(plan=plan, terminal_kinds=terminal_kinds)
        if not feasible:
            # Defensive: the planner's reverse-BFS pruning guarantees that any
            # non-empty plan has at least one depth reaching the terminal
            raise ValueError("plan has adjacency but no feasible fixed-depth branch within max_depth")

        phase_two_inner = "\n  UNION ALL\n".join(
            self._render_phase_two_branch(b, terminal_label_union=terminal_label_union) for b in feasible
        )

        if terminal_anchored_by_id:
            text = _PATH_TRAVERSAL_ENVELOPE % {
                "source_match": _SOURCE_MATCH,
                "target_match": _TARGET_BY_ID_MATCH,
                "phase_two_inner": phase_two_inner,
            }
        else:
            phase_one_inner = "\n  UNION\n".join(
                self._render_phase_one_branch(b, terminal_label_union=terminal_label_union) for b in feasible
            )
            text = _REACHABLE_NODES_ENVELOPE % {
                "source_match": _SOURCE_MATCH,
                "phase_one_inner": phase_one_inner,
                "phase_two_inner": phase_two_inner,
            }

        params: dict[str, Any] = {
            "source_id": source_id,
            "at": self._at.to_string(),
            "valid_branches": self._valid_branches,
            "max_targets": self._max_targets,
            "max_paths": self._max_paths,
        }
        for branch_data in feasible:
            for hop_idx, hop_tuples in enumerate(branch_data.tuples_per_hop, start=1):
                params[branch_data.hop_tuple_param(hop_idx)] = [list(t) for t in hop_tuples]
        if isinstance(plan.terminal_predicate, TerminalById):
            params["target_id"] = plan.terminal_predicate.node_id
        if self._is_user_branch:
            params["user_branch"] = self._user_branch_name

        return RenderedCypher(text=text, params=params, return_labels=_RETURN_LABELS)

    def _build_feasible_branches(self, *, plan: Plan, terminal_kinds: frozenset[str]) -> list[_DepthBranchData]:
        """Compute per-depth structure once. Both phases consume the same data."""
        feasible: list[_DepthBranchData] = []
        for depth in range(1, plan.max_depth + 1):
            per_step = self._per_step_kinds_for_depth(plan=plan, depth=depth)
            tuples_per_hop = self._hop_tuples_for_depth(
                plan=plan, terminal_kinds=terminal_kinds, depth=depth, per_step_kinds=per_step
            )
            if tuples_per_hop is None:
                continue
            feasible.append(_DepthBranchData(depth=depth, per_step_kinds=per_step, tuples_per_hop=tuples_per_hop))
        return feasible

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

    def _render_phase_one_branch(self, branch_data: _DepthBranchData, *, terminal_label_union: str) -> str:
        """Phase 1 per-depth branch: chained DISTINCT-capped CALLs returning ``target``.

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
        depth = branch_data.depth
        parts: list[str] = []
        accumulated: list[str] = ["source"]
        for hop in range(1, depth + 1):
            from_var = "source" if hop == 1 else f"b{hop - 1}"
            to_var = "target" if hop == depth else f"b{hop}"
            to_pattern = self._end_node_pattern(
                branch_data=branch_data, hop=hop, to_var=to_var, terminal_label_union=terminal_label_union
            )
            r_in, rel_var, r_out = "ra", "rel", "rb"
            # Phase 1 source-excludes every hop's destination, including the
            # terminal — so $source_id never enters terminal_uuids.
            preds = self._hop_predicates(
                branch_data=branch_data,
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

    def _render_phase_two_branch(self, branch_data: _DepthBranchData, *, terminal_label_union: str) -> str:
        """Phase 2 per-depth branch: fixed-length ``MATCH`` constrained to ``target.uuid IN terminal_uuids``.

        For depth-``d`` paths, builds a single ``MATCH`` with ``2d`` IS_RELATED
        edges and ``d`` Relationship vertices. Each hop carries the per-hop
        triple predicate, edge active/branch filters, deletion-shadow checks on
        user branches, and intermediate distinctness checks.

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
            RETURN source.uuid AS start_node_uuid, source.kind AS start_node_kind,
                   [{rel_id: rel1.name, uuid: b1.uuid, kind: b1.kind},
                    {rel_id: rel2.name, uuid: b2.uuid, kind: b2.kind},
                    {rel_id: rel3.name, uuid: target.uuid, kind: target.kind}] AS hops,
                   3 AS depth
        """
        depth = branch_data.depth
        path_segs: list[str] = ["(source)"]
        preds: list[str] = ["target.uuid IN terminal_uuids"]
        for hop in range(1, depth + 1):
            r_s, rel_var, r_e = f"r{hop}_s", f"rel{hop}", f"r{hop}_e"
            from_var = "source" if hop == 1 else f"b{hop - 1}"
            to_var = "target" if hop == depth else f"b{hop}"
            to_pattern = self._end_node_pattern(
                branch_data=branch_data, hop=hop, to_var=to_var, terminal_label_union=terminal_label_union
            )
            path_segs.append(f"-[{r_s}:IS_RELATED]-({rel_var}:Relationship)-[{r_e}:IS_RELATED]-{to_pattern}")
            # Phase 2 source-excludes intermediates only b/c target is
            # constrained by ``target.uuid IN terminal_uuids`` and Phase 1
            # filtered $source_id out of terminal_uuids
            preds.extend(
                self._hop_predicates(
                    branch_data=branch_data,
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
        self, *, branch_data: _DepthBranchData, hop: int, to_var: str, terminal_label_union: str
    ) -> str:
        """Return the ``(var:Labels)`` pattern fragment for the destination node at ``hop``."""
        if hop < branch_data.depth:
            return f"({to_var}:{'|'.join(branch_data.per_step_kinds[hop - 1])})"
        return f"(target:{terminal_label_union})"

    def _hop_predicates(
        self,
        *,
        branch_data: _DepthBranchData,
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
        is_intermediate = hop < branch_data.depth
        preds: list[str] = [_EDGE_ACTIVE_PREDICATE.format(rv=rv) for rv in (r_in, r_out)]
        preds.append(
            _HOP_TUPLE_PREDICATE.format(
                start_var=from_var,
                rel_var=rel_var,
                end_var=to_var,
                hop_tuple_param=branch_data.hop_tuple_param(hop),
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

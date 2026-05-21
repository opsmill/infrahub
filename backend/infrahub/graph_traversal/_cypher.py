"""Internal Cypher renderer for the graph-traversal planner.

Pure function over a ``Plan``. No I/O. No async.

A single quantified-path-pattern (QPP) MATCH covers both default-branch and
user-branch requests. The planner-derived ``$allowed_path_maps`` parameter
encodes every approved ``(start_kind, rel_name, end_kind)`` triple and gates
each QPP iteration. The only branch-conditional pieces are:

- ``$valid_branches``: ``[default, global]`` on the default branch;
  ``[default, global, user]`` on a user branch.
- The user-branch query adds two ``NOT EXISTS`` deletion checks (and binds
  ``$user_branch``). The default branch has no version race to resolve, so
  the deletion check is unnecessary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.graph_traversal.planning.models import Plan, TerminalById

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp


_RETURN_LABELS: tuple[str, ...] = ("path_data", "depth")

_MIN_RESULTS = 1
_MAX_RESULTS = 200


@dataclass(frozen=True, slots=True)
class RenderedCypher:
    text: str
    params: dict[str, Any]
    return_labels: tuple[str, ...]


# ============================================================================
# Cypher templates
# ============================================================================


_QPP_BODY = """
  (a:%(start_labels)s)-[r1:IS_RELATED]-(rel:Relationship)-[r2:IS_RELATED]-(b:%(end_labels)s)
  WHERE rel.name IN $all_rel_names
    AND r1.branch IN $valid_branches AND r1.status = "active"
    AND r1.from <= $at AND (r1.to IS NULL OR r1.to >= $at)
    AND r2.branch IN $valid_branches AND r2.status = "active"
    AND r2.from <= $at AND (r2.to IS NULL OR r2.to >= $at)%(deletion_filter)s
    AND rel.name IN keys($allowed_path_maps[a.kind])
    AND b.kind IN $allowed_path_maps[a.kind][rel.name]"""


_USER_BRANCH_QPP_DELETION_FILTER = """

    // ----------------
    // account for objects active on default/global and deleted on the user's branch
    // ----------------
    AND NOT EXISTS {
      (a)-[del:IS_RELATED {status: "deleted", branch: $user_branch}]-(rel)
      WHERE del.from > r1.from
        AND del.from <= $at
        AND (del.to IS NULL OR del.to >= $at)
    }
    AND NOT EXISTS {
      (rel)-[del:IS_RELATED {status: "deleted", branch: $user_branch}]-(b)
      WHERE del.from > r2.from
        AND del.from <= $at
        AND (del.to IS NULL OR del.to >= $at)
    }"""

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

# Outer envelope. Sadly, the QPP min and max length must be literal integers and cannot
# be parameters. ``path_data`` projects only the ``uuid``/``kind``/``name``
# properties the caller reads — the heavy Neo4j Path object is not returned.
_QUERY = """
%(source_match)s%(target_match)s
MATCH path = (source) (
%(qpp_body)s
){1, %(max_path_length)d} %(target_pattern)s
WITH path, length(path) / 2 AS depth
ORDER BY depth ASC, path
LIMIT $max_results
RETURN
    [n IN nodes(path) | {uuid: n.uuid, kind: n.kind, name: n.name}] AS path_data,
    depth
"""


# ============================================================================
# Assembly
# ============================================================================


def render_plan_to_cypher(
    *,
    plan: Plan,
    source_id: str,
    branch: Branch,
    at: Timestamp,
    max_results: int,
) -> RenderedCypher:
    """Render a non-empty Plan as a single QPP-based Cypher query.

    Raises:
        ValueError: when ``plan`` is empty or ``max_results`` is out of range.
    """
    if plan.is_empty:
        raise ValueError("plan has no adjacency")
    if not _MIN_RESULTS <= max_results <= _MAX_RESULTS:
        raise ValueError(f"max_results must be in [{_MIN_RESULTS}, {_MAX_RESULTS}], got {max_results}")

    allowed_path_maps: dict[str, dict[str, list[str]]] = {
        start_kind: {rel_name: sorted(end_kinds) for rel_name, end_kinds in rels.items()}
        for start_kind, rels in plan.adjacency.items()
    }
    all_rel_names = sorted({rn for rels in allowed_path_maps.values() for rn in rels})
    start_kinds = sorted(allowed_path_maps)
    end_kinds = sorted({ek for rels in allowed_path_maps.values() for eks in rels.values() for ek in eks})

    if branch.is_default:
        valid_branches = [registry.default_branch, GLOBAL_BRANCH_NAME]
        qpp_deletion_filter = ""
    else:
        valid_branches = [registry.default_branch, GLOBAL_BRANCH_NAME, branch.name]
        qpp_deletion_filter = _USER_BRANCH_QPP_DELETION_FILTER

    params: dict[str, Any] = {
        "source_id": source_id,
        "at": at.to_string(),
        "valid_branches": valid_branches,
        "all_rel_names": all_rel_names,
        "allowed_path_maps": allowed_path_maps,
        "max_results": max_results,
    }
    if not branch.is_default:
        params["user_branch"] = branch.name

    if isinstance(plan.terminal_predicate, TerminalById):
        params["target_id"] = plan.terminal_predicate.node_id
        target_match = _TARGET_BY_ID_MATCH
        target_pattern = "(target)"
    else:
        params["terminal_kinds"] = sorted(plan.terminal_predicate.kinds)
        target_match = ""
        target_pattern = "(target:$any($terminal_kinds))"

    qpp_body = _QPP_BODY % {
        "start_labels": "|".join(start_kinds),
        "end_labels": "|".join(end_kinds),
        "deletion_filter": qpp_deletion_filter,
    }
    text = _QUERY % {
        "source_match": _SOURCE_MATCH,
        "target_match": target_match,
        "qpp_body": qpp_body,
        "max_path_length": plan.max_depth,
        "target_pattern": target_pattern,
    }
    return RenderedCypher(text=text, params=params, return_labels=_RETURN_LABELS)

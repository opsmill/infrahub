from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp

_AT_PARAM = "vertex_updated_metadata_at"
_BRANCHES_PARAM = "vertex_updated_metadata_branches"


def build_vertex_updated_metadata_query(
    vertex: str, edges_pattern: str, at: Timestamp, carry: str = "*"
) -> tuple[str, dict[str, Any]]:
    """Return a query fragment and its parameters exposing `updated_at` and `updated_by` of `vertex` as of `at`.

    The vertex only stores its latest update, which is correct when that update happened at or before `at`;
    otherwise the values come from the latest edge created or closed on the default branch by `at`, among the
    edges that `edges_pattern` binds as `r`, because closing an edge without creating one is also an update.
    """
    query = f"""
OPTIONAL CALL ({vertex}) {{
    WITH {vertex}
    WHERE {vertex}.updated_at > ${_AT_PARAM}
    {edges_pattern}
    WHERE r.branch IN ${_BRANCHES_PARAM} AND r.from <= ${_AT_PARAM}
    UNWIND CASE
        WHEN r.to IS NOT NULL AND r.to <= ${_AT_PARAM} THEN [[r.from, r.from_user_id], [r.to, r.to_user_id]]
        ELSE [[r.from, r.from_user_id]]
    END AS change
    RETURN change[0] AS edge_updated_at, change[1] AS edge_updated_by
    ORDER BY edge_updated_at DESC, edge_updated_by DESC
    LIMIT 1
}}
WITH {carry},
    CASE
        WHEN {vertex}.updated_at > ${_AT_PARAM} THEN edge_updated_at
        ELSE {vertex}.updated_at
    END AS updated_at,
    CASE
        WHEN {vertex}.updated_at > ${_AT_PARAM} THEN edge_updated_by
        ELSE {vertex}.updated_by
    END AS updated_by
"""
    params = {_AT_PARAM: at.to_string(), _BRANCHES_PARAM: [registry.default_branch, GLOBAL_BRANCH_NAME]}
    return query, params

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp

_AT_PARAM = "vertex_updated_metadata_at"


def build_vertex_updated_metadata_query(
    vertex: str, edges_query: str, at: Timestamp, carry: str = "*"
) -> tuple[str, dict[str, Any]]:
    """Return a query fragment and its parameters exposing `updated_at` and `updated_by` of `vertex` as of `at`.

    The vertex only stores its latest update, which is correct when that update happened at or before `at`;
    otherwise the values come from the latest edge returned by `edges_query`, which must bind the edges as `r`
    and filter them on the queried branch and time.
    """
    query = f"""
OPTIONAL CALL ({vertex}) {{
    WITH {vertex}
    WHERE {vertex}.updated_at > ${_AT_PARAM}
    {edges_query}
    RETURN r.from AS edge_updated_at, r.from_user_id AS edge_updated_by
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
    return query, {_AT_PARAM: at.to_string()}

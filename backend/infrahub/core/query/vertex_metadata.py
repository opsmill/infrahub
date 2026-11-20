from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.timestamp import Timestamp


def stamp_vertex_metadata(
    variable: str, at: Timestamp, operation_ats: Sequence[Timestamp], at_param: str = "at"
) -> tuple[str, dict[str, list[str]]]:
    """Return the Cypher that records `$<at_param>` and `$user_id` as a vertex's last change, and the parameters it needs.

    The Cypher keeps the stamp it replaces as the previous one. The previous stamp is what a rollback restores,
    so a write leaves it alone when the vertex was last stamped by the same operation, at one of the timestamps
    in `$operation_ats`.

    `at` must be the timestamp bound to `$<at_param>`, because it only feeds the `operation_ats` parameter.

    The returned `operation_ats` parameter holds `operation_ats` and `at`, as strings, so a write always
    recognizes its own stamp. Every call in one query returns the same parameters, so the caller merges them
    into the query's parameters.
    """
    text = f"""
    SET {variable}.previous_updated_at = CASE
            WHEN {variable}.updated_at IS NULL OR NOT {variable}.updated_at IN $operation_ats THEN {variable}.updated_at
            ELSE {variable}.previous_updated_at
        END,
        {variable}.previous_updated_by = CASE
            WHEN {variable}.updated_at IS NULL OR NOT {variable}.updated_at IN $operation_ats THEN {variable}.updated_by
            ELSE {variable}.previous_updated_by
        END
    SET {variable}.updated_at = ${at_param}, {variable}.updated_by = $user_id
    """
    params = {"operation_ats": list(dict.fromkeys([ts.to_string() for ts in operation_ats] + [at.to_string()]))}
    return text, params

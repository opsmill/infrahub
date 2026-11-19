from __future__ import annotations


def stamp_vertex_metadata(variable: str, at_param: str = "at") -> str:
    """Cypher that records `$<at_param>` and `$user_id` as a vertex's last change, keeping the stamp it replaces as the previous one.

    The previous stamp is what a rollback restores, so a write leaves it alone when the vertex was last stamped
    by the same operation, at one of the timestamps in `$operation_ats`.
    """
    return f"""
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

from __future__ import annotations


def stamp_vertex_metadata(variable: str) -> str:
    """Cypher that records `$at` and `$user_id` as a vertex's last change, keeping the stamp it replaces as the previous one.

    The previous stamp is what a rollback restores, so a second write at the same `$at` leaves it alone.
    """
    return f"""
    SET {variable}.previous_updated_at = CASE
            WHEN {variable}.updated_at IS NULL OR {variable}.updated_at <> $at THEN {variable}.updated_at
            ELSE {variable}.previous_updated_at
        END,
        {variable}.previous_updated_by = CASE
            WHEN {variable}.updated_at IS NULL OR {variable}.updated_at <> $at THEN {variable}.updated_by
            ELSE {variable}.previous_updated_by
        END
    SET {variable}.updated_at = $at, {variable}.updated_by = $user_id
    """

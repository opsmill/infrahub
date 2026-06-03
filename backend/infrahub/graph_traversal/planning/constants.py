"""Constants for the graph-traversal planner."""

from __future__ import annotations

MIN_DEPTH = 1
MAX_DEPTH = 20

DEFAULT_EXCLUDED_NAMESPACES: tuple[str, ...] = (
    "Core",
    "Internal",
    "Builtin",
    "Lineage",
    "Profile",
    "Template",
)

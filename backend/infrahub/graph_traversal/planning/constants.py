"""Constants for the graph-traversal planner."""

from __future__ import annotations

from infrahub.core.constants import InfrahubKind

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

DEFAULT_EXCLUDED_KINDS: tuple[str, ...] = (InfrahubKind.IPNAMESPACE,)

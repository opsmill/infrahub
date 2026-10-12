from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from infrahub.core.schema.manager import SchemaManager


class ModifiedKindsExpander(Protocol):
    """Widens the changed kinds a regeneration selection considers, beyond those literally in the diff."""

    def expand(self, *, modified_kinds: list[str], branch: str) -> list[str]: ...


class SchemaProfileExpander:
    """Widen changed kinds with the node kind behind each changed profile, from a branch's live schema.

    A profile holds attribute values that apply to the nodes it targets, so changing a profile node
    effectively changes those nodes. A profile schema's name is the kind of the node it targets, so a
    changed profile widens the set to that node kind; a kind that names no profile passes through.
    """

    def __init__(self, schema_manager: SchemaManager) -> None:
        self._schema_manager = schema_manager

    def expand(self, *, modified_kinds: list[str], branch: str) -> list[str]:
        schema_branch = self._schema_manager.get_schema_branch(name=branch)
        expanded = set(modified_kinds)
        for kind in modified_kinds:
            if kind in schema_branch.profiles:
                expanded.add(schema_branch.get_profile(name=kind, duplicate=False).name)
        return list(expanded)

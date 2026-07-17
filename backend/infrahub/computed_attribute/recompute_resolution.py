from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from infrahub.core.schema.schema_branch_computed import PythonDefinition


class RecomputeResolver:
    """Resolve a Python transform to the computed attributes it feeds.

    A computed attribute wires its transform by name or UUID, so both keys are checked.
    """

    def __init__(self, attributes_by_transform: Mapping[str, list[PythonDefinition]]) -> None:
        self._attributes_by_transform = attributes_by_transform

    def resolve(self, transform_name: str, transform_id: str) -> list[PythonDefinition]:
        # A transform can be wired by name for one attribute and by id for another, so union both
        # lookups (not short-circuit) and dedupe by (kind, attribute) to avoid a double recompute.
        resolved: list[PythonDefinition] = []
        seen: set[tuple[str, str]] = set()
        for key in (transform_name, transform_id):
            for definition in self._attributes_by_transform.get(key) or []:
                identity = (definition.kind, definition.attribute.name)
                if identity not in seen:
                    seen.add(identity)
                    resolved.append(definition)
        return resolved

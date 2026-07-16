from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch_computed import PythonDefinition


class TransformAttributeMap(Protocol):
    """The transform -> computed-attributes lookup the resolver reads, keyed by name or id."""

    def get(self, key: str, /) -> list[PythonDefinition] | None: ...


class RecomputeResolver:
    """Resolve a Python transform to the computed attributes it feeds.

    A computed attribute wires its transform by either a name or a UUID, and the
    lookup mapping is keyed by that raw value, so the resolution checks both. A
    transform that feeds nothing resolves to an empty list from the mapping lookup
    alone, without touching the database or the client.
    """

    def __init__(self, attributes_by_transform: TransformAttributeMap) -> None:
        self._attributes_by_transform = attributes_by_transform

    def resolve(self, transform_name: str, transform_id: str) -> list[PythonDefinition]:
        return (
            self._attributes_by_transform.get(transform_name) or self._attributes_by_transform.get(transform_id) or []
        )

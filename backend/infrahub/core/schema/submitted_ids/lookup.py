from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Collection


class SchemaElementIdLookup(Protocol):
    """Finds which IDs belong to a schema element that has ever existed."""

    async def get_existing_ids(self, ids: Collection[str]) -> set[str]:
        """Return the subset of ``ids`` held by a schema element on any branch, at any time."""
        ...

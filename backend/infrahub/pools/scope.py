from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from infrahub.exceptions import ValidationError


@dataclass(frozen=True)
class ScopeElement:
    """An attribute or a relationship of the pool's kind, referenced by its schema id and shown by its name."""

    id: str
    name: str

    def to_stored(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True)
class AllocationScope:
    """The ordered elements that divide a pool's space; no element means the pool allocates from one space."""

    elements: tuple[ScopeElement, ...] = ()

    @classmethod
    def from_stored(cls, value: object, pool: str) -> AllocationScope:
        """Read the scope stored on `pool`, absent or empty meaning unscoped.

        Raises:
            ValidationError: the value is not a list, or an entry is not an object holding a text `id` and a
                text `name`.

        """
        if value is None:
            entries: list[Any] = []
        elif isinstance(value, list):
            entries = value
        else:
            raise ValidationError(
                f"allocation_scope of pool {pool}: the stored value {json.dumps(value, default=repr)} is not a list "
                "of elements; recreate the pool to set its scope"
            )
        elements: list[ScopeElement] = []
        for entry in entries:
            if not (
                isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("name"), str)
            ):
                raise ValidationError(
                    f"allocation_scope of pool {pool}: the stored entry {json.dumps(entry, default=repr)} is not an element "
                    'with an "id" and a "name"; recreate the pool to set its scope'
                )
            elements.append(ScopeElement(id=entry["id"], name=entry["name"]))
        return cls(elements=tuple(elements))

    def to_stored(self) -> list[dict[str, str]]:
        return [element.to_stored() for element in self.elements]

    @property
    def is_empty(self) -> bool:
        return not self.elements

    @property
    def element_names(self) -> tuple[str, ...]:
        return tuple(element.name for element in self.elements)


@dataclass(frozen=True, eq=False)
class Division:
    """The values a holder has for the scope elements, in scope order; one division is one space of the pool.

    Two divisions are equal when their values have the same JSON form, so a list or a document only matches
    the same list or document, and 1, 1.0 and true are three different values.
    """

    values: tuple[Any, ...]

    @property
    def key(self) -> str:
        """Return a hash of the values that stays the same across processes, used to name the division's lock."""
        # Sorted keys make the hash ignore the key order of a document, as its equality does.
        encoded = json.dumps(list(self.values), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("ascii")).hexdigest()

    # Equality and hashing follow the lock key, so equal divisions share one lock and list values stay hashable.
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Division):
            return NotImplemented
        return self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)

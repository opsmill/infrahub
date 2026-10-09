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


@dataclass(frozen=True)
class Division:
    """The values an object has for the scope elements, in scope order; one division is one space of the pool.

    A scope element is a relationship or a scalar attribute, so each value is a peer id or a scalar as stored.
    """

    values: tuple[str | int | float | bool, ...]

    @property
    def key(self) -> str:
        """Return a hash of the values that stays the same across processes, used to name the division's lock."""
        encoded = json.dumps(list(self.values), separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("ascii")).hexdigest()

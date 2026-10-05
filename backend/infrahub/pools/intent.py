from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FromPoolIntent(Enum):
    """What a write naming a number pool on an attribute asks the pool to do."""

    ALLOCATE = "allocate"
    ATTACH = "attach"
    DETACH = "detach"
    NO_OP = "no_op"
    REFUSE = "refuse"


@dataclass(frozen=True)
class FromPoolRequest:
    """A write's `value` and `from_pool`, told apart by presence, against the attribute's current state."""

    value_present: bool
    value: int | None
    from_pool_present: bool
    from_pool_id: str | None
    """The resolved pool id; `None` with `from_pool_present` is an explicit `null`."""
    held_value_is_default: bool
    """Whether the number the attribute holds is its schema default; read only when the write sends no value."""
    tracking_pool_id: str | None
    """The pool currently tracking the attribute, if any."""
    held_value: int | None
    """The number the attribute holds; read only when the write sends no value."""

    def __post_init__(self) -> None:
        if not self.value_present and self.value is not None:
            raise ValueError("A value cannot be carried without being present in the payload.")
        if not self.from_pool_present and self.from_pool_id is not None:
            raise ValueError("A pool cannot be carried without from_pool being present in the payload.")


class FromPoolIntentResolver:
    """Decide what a write naming a number pool means, without reading the database."""

    def resolve(self, request: FromPoolRequest) -> FromPoolIntent:
        if not request.from_pool_present:
            return FromPoolIntent.NO_OP
        if request.from_pool_id is None:
            return FromPoolIntent.DETACH if request.tracking_pool_id is not None else FromPoolIntent.NO_OP
        # Moving to another pool is the same write as attaching or allocating, since writing a pool's
        # reservation ends any other pool's on the attribute.
        if request.value_present:
            return FromPoolIntent.ALLOCATE if request.value is None else FromPoolIntent.ATTACH
        return self._resolve_pool_alone(request=request)

    def _resolve_pool_alone(self, request: FromPoolRequest) -> FromPoolIntent:
        if request.tracking_pool_id == request.from_pool_id:
            return FromPoolIntent.NO_OP
        # Overwriting a number nobody asked the pool to replace is ambiguous between attach and reallocate.
        if request.tracking_pool_id is None and request.held_value is not None and not request.held_value_is_default:
            return FromPoolIntent.REFUSE
        return FromPoolIntent.ALLOCATE

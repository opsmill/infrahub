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
class Sent[T]:
    """A payload field that was sent; `value` is `None` when it was sent as an explicit `null`."""

    value: T | None


@dataclass(frozen=True)
class FromPoolRequest:
    """A write's `value` and `from_pool`, told apart by presence, against the attribute's current state."""

    value: Sent[int] | None
    """`None` when the write leaves `value` out."""
    from_pool: Sent[str] | None
    """The resolved pool id; `None` when the write leaves `from_pool` out."""
    held_value_is_default: bool
    """Whether the number the attribute holds is its schema default; read only when the write sends no value."""
    tracking_pool_id: str | None
    """The pool currently tracking the attribute, if any."""
    held_value: int | None
    """The number the attribute holds; read only when the write sends no value."""


class FromPoolIntentResolver:
    """Decide what a write naming a number pool means, without reading the database."""

    def resolve(self, request: FromPoolRequest) -> FromPoolIntent:
        if request.from_pool is None:
            return FromPoolIntent.NO_OP
        if request.from_pool.value is None:
            return FromPoolIntent.DETACH if request.tracking_pool_id is not None else FromPoolIntent.NO_OP
        # Moving to another pool is the same write as attaching or allocating, since writing a pool's
        # reservation ends any other pool's on the attribute.
        if request.value is not None:
            return FromPoolIntent.ALLOCATE if request.value.value is None else FromPoolIntent.ATTACH
        if request.tracking_pool_id == request.from_pool.value:
            return FromPoolIntent.NO_OP
        # A pool named over a number the attribute holds could mean attach it or replace it.
        if request.held_value is not None and not request.held_value_is_default:
            return FromPoolIntent.REFUSE
        return FromPoolIntent.ALLOCATE

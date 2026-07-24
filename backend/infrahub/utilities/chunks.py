"""Split a sequence into contiguous fixed-size batches."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Iterator


@overload
def chunked[T](items: list[T], size: int) -> Iterator[list[T]]: ...


@overload
def chunked[T](items: tuple[T, ...], size: int) -> Iterator[tuple[T, ...]]: ...


def chunked[T](items: list[T] | tuple[T, ...], size: int) -> Iterator[list[T] | tuple[T, ...]]:
    """Yield ``items`` in contiguous slices of at most ``size``, preserving the input type."""
    for start in range(0, len(items), size):
        yield items[start : start + size]

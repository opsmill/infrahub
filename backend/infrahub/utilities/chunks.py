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
    """Yield ``items`` in contiguous slices of at most ``size``, preserving the input type.

    Raises:
        ValueError: if ``size`` is not positive. A non-positive size cannot produce slices and
            would otherwise either blow up inside ``range`` or silently drop every item.

    """
    if size <= 0:
        raise ValueError(f"chunk size must be greater than zero, got {size}")
    for start in range(0, len(items), size):
        yield items[start : start + size]

"""Pagination helper that exists only in the bug-pipeline sandbox, where the sandbox test plants it."""

from __future__ import annotations


def count_pages(total_items: int, page_size: int) -> int:
    """Return how many pages are needed to list `total_items` items with `page_size` items per page.

    Raises:
        ValueError: If `page_size` is below 1 or `total_items` is negative.

    """
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    if total_items < 0:
        raise ValueError("total_items cannot be negative")
    return total_items // page_size

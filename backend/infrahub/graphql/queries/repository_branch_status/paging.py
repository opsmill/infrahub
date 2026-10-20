from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.branch.models import Branch
    from infrahub.core.query.repository import RepositoryBranchAttributeValue


@dataclass(frozen=True)
class RepositoryBranchStatusRow:
    """One branch and the repository attribute values that branch resolves."""

    branch: Branch
    """Branch the row reports on."""

    values: Mapping[str, RepositoryBranchAttributeValue]
    """Resolved attribute values, keyed by attribute name."""


def apply_value_filters(
    rows: Sequence[RepositoryBranchStatusRow],
    sync_status: str | None,
    internal_status: str | None,
    own_values_only: bool,
) -> list[RepositoryBranchStatusRow]:
    """Narrow rows by resolved attribute value.

    Args:
        rows: Rows to filter.
        sync_status: Keep rows whose resolved `sync_status` equals this value; no constraint when None.
        internal_status: Keep rows whose resolved `internal_status` equals this value; no constraint when None.
        own_values_only: Keep only rows holding their own `commit` value rather than an inherited one.

    Returns:
        The rows that satisfy every given constraint, in their original order.

    """
    kept: list[RepositoryBranchStatusRow] = []
    for row in rows:
        if sync_status is not None and _value_of(row=row, attribute_name="sync_status") != sync_status:
            continue
        if internal_status is not None and _value_of(row=row, attribute_name="internal_status") != internal_status:
            continue
        if own_values_only:
            commit = row.values.get("commit")
            if commit is None or not commit.own_value:
                continue
        kept.append(row)
    return kept


def order_rows(rows: Sequence[RepositoryBranchStatusRow]) -> list[RepositoryBranchStatusRow]:
    """Return the rows with the default branch first, then by branch name ascending."""
    return sorted(rows, key=lambda row: (not row.branch.is_default, row.branch.name))


def page_rows(rows: Sequence[RepositoryBranchStatusRow], offset: int, limit: int) -> list[RepositoryBranchStatusRow]:
    """Return one page of rows, empty when the offset is past the end."""
    return list(rows[offset : offset + limit])


def _value_of(row: RepositoryBranchStatusRow, attribute_name: str) -> str | None:
    value = row.values.get(attribute_name)
    return value.value if value else None

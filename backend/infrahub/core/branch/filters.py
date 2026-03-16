from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from infrahub.core.branch.enums import BranchStatus


@dataclass(slots=True)
class BranchListFilters:
    """Encapsulates all branch list query filters.

    This dataclass is constructed in the GraphQL layer and passed through
    to the core query layer. It follows the pattern established by
    StandardNodeOrdering for passing structured data through layers.

    Timestamp fields use datetime objects (converted from GraphQL DateTime scalar).
    The query layer converts these to Infrahub timestamp strings for Cypher comparison.
    """

    name: str | None = None
    ids: list[str] | None = field(default=None)
    partial_match: bool = False
    status: BranchStatus | None = None
    created_by_id: str | None = None
    branched_from_after: datetime | None = None
    branched_from_before: datetime | None = None
    created_at_after: datetime | None = None
    created_at_before: datetime | None = None
    updated_at_after: datetime | None = None
    updated_at_before: datetime | None = None

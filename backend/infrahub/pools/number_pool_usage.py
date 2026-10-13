"""The utilization, the divisions and the tracked numbers of one number pool, as the dedicated queries report them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.constants import PoolRecordProvenance
    from infrahub.pools.number import UtilizationFigures
    from infrahub.pools.scope import ScopeElement


@dataclass(frozen=True)
class RangeUsage:
    id: str
    display_label: str
    start: int
    end: int
    weight: int
    figures: UtilizationFigures


@dataclass(frozen=True)
class PoolUsage:
    id: str
    display_label: str
    allocation_scope: tuple[ScopeElement, ...]
    figures: UtilizationFigures
    ranges: tuple[RangeUsage, ...]


@dataclass(frozen=True)
class DivisionEntry:
    id: str
    path: str
    value: str | float | bool
    display_label: str
    peer_kind: str | None


@dataclass(frozen=True)
class DivisionUsage:
    display_label: str
    entries: tuple[DivisionEntry, ...]
    figures: UtilizationFigures


@dataclass(frozen=True)
class PoolDivisions:
    count: int
    allocation_scope: tuple[ScopeElement, ...]
    divisions: tuple[DivisionUsage, ...]


@dataclass(frozen=True)
class PeerSummary:
    display_label: str
    kind: str


@dataclass(frozen=True)
class HoldingObject:
    id: str
    hfid: list[str] | None
    kind: str
    display_label: str


@dataclass(frozen=True)
class RangeReference:
    id: str
    display_label: str


@dataclass(frozen=True)
class TrackedNumber:
    value: int
    branch: str
    holder: HoldingObject
    identifier: str
    provenance: PoolRecordProvenance
    range: RangeReference


@dataclass(frozen=True)
class TrackedNumbersPage:
    count: int
    allocations: tuple[TrackedNumber, ...]

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True, slots=True)
class UnresolvedRef:
    file: str
    location: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ClosureResult:
    dependencies: tuple[str, ...]
    complete: bool
    unresolved: tuple[UnresolvedRef, ...]

"""In-memory doubles for the Python target resolution collaborators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.merge.recompute_coalescing import CoalescedRecompute
    from infrahub.core.schema.schema_branch_computed import TransformReadSet
    from infrahub.core.timestamp import Timestamp


class LookupUnavailableError(Exception):
    """Raised by the failing doubles to stand in for an unreachable or slow lookup."""


@dataclass
class RecordingReadFieldIndex:
    """Returns a canned read-field index and records which branches were asked for."""

    index: dict[tuple[str, str], TransformReadSet] = field(default_factory=dict)
    branches: list[str] = field(default_factory=list)

    async def for_branch(self, *, branch: str) -> dict[tuple[str, str], TransformReadSet]:
        self.branches.append(branch)
        return self.index


@dataclass
class FailingReadFieldIndex:
    """Fails the way an unreachable database does, to prove the caller widens rather than skips."""

    async def for_branch(self, *, branch: str) -> dict[tuple[str, str], TransformReadSet]:
        raise LookupUnavailableError(f"read-field index unavailable for {branch}")


@dataclass
class RecordingSubscriberLookup:
    """Returns canned readers and records every call, so a per-node lookup is visible as such."""

    readers: dict[str, frozenset[str]] = field(default_factory=dict)
    calls: list[frozenset[str]] = field(default_factory=list)

    async def readers_of(
        self, *, node_ids: frozenset[str], branch: str, at: Timestamp | None
    ) -> dict[str, frozenset[str]]:
        self.calls.append(node_ids)
        return dict(self.readers)


@dataclass
class FailingSubscriberLookup:
    """Fails on every call, to prove a lookup failure widens rather than dropping the target."""

    calls: list[frozenset[str]] = field(default_factory=list)

    async def readers_of(
        self, *, node_ids: frozenset[str], branch: str, at: Timestamp | None
    ) -> dict[str, frozenset[str]]:
        self.calls.append(node_ids)
        raise LookupUnavailableError("subscriber lookup unavailable")


@dataclass
class RecordingPythonTargetResolver:
    """Stands in for the whole resolver, so its callers can be tested without a database.

    Returns the coalesced recompute unchanged unless ``result`` is set.
    """

    result: CoalescedRecompute | None = None
    calls: list[tuple[str, Timestamp | None]] = field(default_factory=list)

    async def resolve(
        self, *, coalesced: CoalescedRecompute, branch: str, deleted_at: Timestamp | None
    ) -> CoalescedRecompute:
        self.calls.append((branch, deleted_at))
        return self.result if self.result is not None else coalesced

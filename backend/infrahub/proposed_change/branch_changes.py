from __future__ import annotations

from contextlib import suppress
from datetime import datetime  # noqa: TC003  # Pydantic resolves the field annotations at runtime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # Pydantic resolves the field annotations at runtime

from infrahub_sdk.diff import NodeDiff  # noqa: TC002  # Pydantic resolves the field annotations at runtime
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.timestamp import Timestamp
from infrahub.dependencies.registry import get_component_registry
from infrahub.message_bus.types import KVTTL

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.cache import InfrahubCache


class BranchDiffWindow(BaseModel):
    """A time window of the changes made on a branch."""

    model_config = ConfigDict(frozen=True)

    from_time: datetime
    to_time: datetime


class BranchChanges(BaseModel):
    """The changes made on a branch in a time window, as a diff summary of that window."""

    model_config = ConfigDict(frozen=True)

    diff_summary: list[NodeDiff]
    changed_peers: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    """The peers added to or removed from a relationship, keyed by node id, then by relationship name."""

    def peers_changed(self, *, node_id: str, relationship_name: str) -> set[str]:
        return set(self.changed_peers.get(node_id, {}).get(relationship_name, []))


class BranchChangesReader:
    """Read the changes made on a branch in a time window, from a diff of that window alone.

    The diff of the window is calculated once per pipeline run and kept in the cache for the other
    flows of that run. A cached entry that cannot be read is calculated again.
    """

    def __init__(
        self,
        *,
        diff_coordinator: DiffCoordinator,
        serializer: DiffSummarySerializer,
        cache: InfrahubCache,
        branch: Branch,
        destination_branch: Branch,
        pipeline_id: UUID,
    ) -> None:
        self._diff_coordinator = diff_coordinator
        self._serializer = serializer
        self._cache = cache
        self._branch = branch
        self._destination_branch = destination_branch
        self._pipeline_id = pipeline_id

    async def read(self, window: BranchDiffWindow) -> BranchChanges:
        key = self._key(window=window)
        payload = await self._cache.get(key=key)
        if payload:
            with suppress(ValidationError):
                return BranchChanges.model_validate_json(payload)
        diff = await self._diff_coordinator.calculate_arbitrary_timeframe_diff(
            base_branch=self._destination_branch,
            diff_branch=self._branch,
            from_time=Timestamp(window.from_time.isoformat()),
            to_time=Timestamp(window.to_time.isoformat()),
            include_unchanged=True,
        )
        changes = BranchChanges(
            diff_summary=self._serializer.serialize(
                root=diff, target_branch_name=self._branch.name, unchanged_as_updated=True
            ),
            changed_peers=_changed_peers(diff=diff),
        )
        await self._cache.set(key=key, value=changes.model_dump_json(), expires=KVTTL.TWO_HOURS)
        return changes

    def _key(self, window: BranchDiffWindow) -> str:
        return (
            f"proposed_change:pipeline:pipeline_id:{self._pipeline_id}:branch_changes:"
            f"{window.from_time.isoformat()}:{window.to_time.isoformat()}"
        )


async def build_branch_changes_reader(
    *, db: InfrahubDatabase, cache: InfrahubCache, branch: Branch, destination_branch: Branch, pipeline_id: UUID
) -> BranchChangesReader:
    diff_coordinator = await get_component_registry().get_component(DiffCoordinator, db=db, branch=branch)
    return BranchChangesReader(
        diff_coordinator=diff_coordinator,
        serializer=DiffSummarySerializer(),
        cache=cache,
        branch=branch,
        destination_branch=destination_branch,
        pipeline_id=pipeline_id,
    )


def _changed_peers(diff: EnrichedDiffRoot) -> dict[str, dict[str, list[str]]]:
    changed_peers: dict[str, dict[str, list[str]]] = {}
    for node in diff.nodes:
        for relationship in node.relationships:
            peer_ids = sorted(element.peer_id for element in relationship.relationships)
            if peer_ids:
                changed_peers.setdefault(node.identifier.uuid, {})[relationship.name] = peer_ids
    return changed_peers

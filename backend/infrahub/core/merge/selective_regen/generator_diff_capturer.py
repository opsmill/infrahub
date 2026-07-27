from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from infrahub_sdk.protocols import CoreGeneratorGroup

from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.core.diff.coordinator import DiffCoordinator
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.diff.summary_serializer import DiffSummarySerializer

# A generator tracks the nodes it writes into a per-member group named "<definition name>-<md5 hex>".
_TRACKING_HASH = re.compile(r"[0-9a-f]{32}$")


class GeneratorMutationDiffCapturer(Protocol):
    """Capture, as a diff summary, the graph changes a post-merge generator wrote.

    A generator dispatched by the post-merge follow-up mutates data after the merge diff was captured,
    so its writes are absent from that diff. Capturing them separately yields the same diff-summary
    shape the regeneration selector consumes, so the artifacts those writes affect can be selected
    precisely instead of regenerating every artifact.
    """

    async def capture(self, *, since: Timestamp, generator_definition_names: list[str]) -> list[NodeDiff]: ...


class GeneratorTrackingGroupDiffCapturer:
    """Capture a post-merge generator's own writes, scoped to the nodes it tracked.

    A time-window diff of the branch alone would also carry any concurrent write landing on it while the
    generators ran. Each generator records the nodes it saves into a tracking group, so intersecting the
    window diff with those nodes yields the generator's own output with per-field detail, free of the
    concurrent noise. When no tracked node can be resolved the window diff is read unscoped, so a lookup
    miss widens the selection rather than dropping a consuming artifact.
    """

    def __init__(
        self,
        diff_coordinator: DiffCoordinator,
        diff_repository: DiffRepository,
        serializer: DiffSummarySerializer,
        client: InfrahubClient,
        branch: Branch,
    ) -> None:
        self.diff_coordinator = diff_coordinator
        self.diff_repository = diff_repository
        self.serializer = serializer
        self.client = client
        self.branch = branch

    async def capture(self, *, since: Timestamp, generator_definition_names: list[str]) -> list[NodeDiff]:
        node_ids = await self._output_node_ids(generator_definition_names=generator_definition_names)

        diff = await self.diff_coordinator.create_or_update_arbitrary_timeframe_diff(
            base_branch=self.branch,
            diff_branch=self.branch,
            from_time=since,
            to_time=Timestamp(),
            name=str(uuid4()),
        )
        filters = EnrichedDiffQueryFilters(ids=sorted(node_ids)) if node_ids else None
        enriched = await self.diff_repository.get_one(
            diff_branch_name=self.branch.name, diff_id=diff.uuid, filters=filters
        )
        return self.serializer.serialize(root=enriched, target_branch_name=self.branch.name)

    async def _output_node_ids(self, *, generator_definition_names: list[str]) -> set[str] | None:
        """Resolve the nodes the just-run generators wrote from their tracking groups on the target branch.

        Returns ``None`` when any requested definition has no resolved tracking group: narrowing on the
        partial aggregate would drop that generator's output, so the caller widens the read instead.
        """
        node_ids: set[str] = set()
        for definition_name in generator_definition_names:
            groups = await self.client.filters(
                kind=CoreGeneratorGroup,
                branch=self.branch.name,
                name__value=definition_name,
                partial_match=True,
                include=["members"],
            )
            matched = [
                group
                for group in groups
                if self._is_tracking_group(group_name=group.name.value, definition_name=definition_name)
            ]
            if not matched:
                return None
            for group in matched:
                node_ids.update(relationship.peer.id for relationship in group.members.peers)
        return node_ids

    def _is_tracking_group(self, *, group_name: str, definition_name: str) -> bool:
        # ``partial_match`` matches any name containing the definition name; keep only this generator's own
        # "<definition name>-<hash>" groups
        suffix = group_name.removeprefix(f"{definition_name}-")
        return suffix != group_name and bool(_TRACKING_HASH.fullmatch(suffix))

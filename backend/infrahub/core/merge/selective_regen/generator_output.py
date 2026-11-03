from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from infrahub_sdk.protocols import CoreGeneratorGroup

from infrahub.core.constants import DiffAction
from infrahub.core.timestamp import Timestamp
from infrahub.generators.models import RequestGeneratorDefinitionRun

from .models import CascadeSourceOutput

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.core.diff.coordinator import DiffCoordinator
    from infrahub.core.diff.model.path import EnrichedDiffRoot
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


class GeneratorCascadeOutput(CascadeSourceOutput[RequestGeneratorDefinitionRun]):
    """The cascade output of a set of generators, captured through their per-member tracking groups.

    Holds only the capturer; the runs to capture arrive per call, so it reads their definition names
    itself and the follow-up need not handle that kind-specific step.
    """

    def __init__(self, capturer: GeneratorMutationDiffCapturer) -> None:
        self._capturer = capturer

    async def capture(self, *, since: Timestamp, requests: Sequence[RequestGeneratorDefinitionRun]) -> list[NodeDiff]:
        definition_names = [run.generator_definition.definition_name for run in requests]
        return await self._capturer.capture(since=since, generator_definition_names=definition_names)


class GeneratorTrackingGroupDiffCapturer(GeneratorMutationDiffCapturer):
    """Capture a post-merge generator's own writes, scoped to the nodes it tracked.

    A time-window diff of the branch alone would also carry any concurrent write landing on it while the
    generators ran. Each generator records the nodes it saves into a tracking group, so calculating the
    window diff for those nodes only yields the generator's own output with per-field detail, free of the
    concurrent noise. A tracked node the generators deleted brings in the peers it was related to, whose
    side of the removed relationships is part of the same output. When no tracked node can be resolved the
    window diff is calculated unscoped, so a lookup miss widens the selection rather than dropping a
    consuming artifact.
    """

    def __init__(
        self,
        diff_coordinator: DiffCoordinator,
        serializer: DiffSummarySerializer,
        client: InfrahubClient,
        branch: Branch,
    ) -> None:
        self.diff_coordinator = diff_coordinator
        self.serializer = serializer
        self.client = client
        self.branch = branch

    async def capture(self, *, since: Timestamp, generator_definition_names: list[str]) -> list[NodeDiff]:
        node_ids = await self._output_node_ids(since=since, generator_definition_names=generator_definition_names)
        until = Timestamp()

        # an empty tracking group widens the read like a missing one, instead of selecting no node
        diff = await self._window_diff(since=since, until=until, node_uuids=node_ids or None)
        if node_ids:
            # Deleting a node also removes its relationships on the side of each peer, which is not tracked.
            peer_ids = _peers_of_deleted_nodes(diff=diff) - node_ids
            if peer_ids:
                diff = await self._window_diff(since=since, until=until, node_uuids=node_ids | peer_ids)
        return self.serializer.serialize(root=diff, target_branch_name=self.branch.name)

    async def _window_diff(
        self, *, since: Timestamp, until: Timestamp, node_uuids: set[str] | None
    ) -> EnrichedDiffRoot:
        return await self.diff_coordinator.calculate_arbitrary_timeframe_diff(
            base_branch=self.branch,
            diff_branch=self.branch,
            from_time=since,
            to_time=until,
            node_uuids=node_uuids,
        )

    async def _output_node_ids(self, *, since: Timestamp, generator_definition_names: list[str]) -> set[str] | None:
        """Resolve the nodes the just-run generators wrote or deleted from their tracking groups on the target branch.

        The groups are read both now and as they were at ``since``: a run deletes the nodes it no longer
        writes, which also drops them from its group, so only the earlier membership still lists them.

        Returns ``None`` when any requested definition has no resolved tracking group now: narrowing on the
        partial aggregate would drop that generator's output, so the caller widens the read instead.
        """
        node_ids: set[str] = set()
        for definition_name in generator_definition_names:
            current = await self._tracking_groups(definition_name=definition_name, at=None)
            if not current:
                return None
            earlier = await self._tracking_groups(definition_name=definition_name, at=since)
            for group in (*current, *earlier):
                node_ids.update(relationship.peer.id for relationship in group.members.peers)
        return node_ids

    async def _tracking_groups(self, *, definition_name: str, at: Timestamp | None) -> list[CoreGeneratorGroup]:
        groups = await self.client.filters(
            kind=CoreGeneratorGroup,
            branch=self.branch.name,
            at=at,
            name__value=definition_name,
            partial_match=True,
            include=["members"],
        )
        return [
            group
            for group in groups
            if self._is_tracking_group(group_name=group.name.value, definition_name=definition_name)
        ]

    def _is_tracking_group(self, *, group_name: str, definition_name: str) -> bool:
        # ``partial_match`` matches any name containing the definition name; keep only this generator's own
        # "<definition name>-<hash>" groups
        suffix = group_name.removeprefix(f"{definition_name}-")
        return suffix != group_name and bool(_TRACKING_HASH.fullmatch(suffix))


def _peers_of_deleted_nodes(*, diff: EnrichedDiffRoot) -> set[str]:
    return {
        element.peer_id
        for node in diff.nodes
        if node.action is DiffAction.REMOVED
        for relationship in node.relationships
        for element in relationship.relationships
    }

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.selective_regen.generator_output import (
    GeneratorCascadeOutput,
    GeneratorTrackingGroupDiffCapturer,
)
from infrahub.core.timestamp import Timestamp
from infrahub.generators.models import ProposedChangeGeneratorDefinition, RequestGeneratorDefinitionRun
from tests.helpers.diff_factories import (
    EnrichedAttributeFactory,
    EnrichedNodeFactory,
    EnrichedRelationshipElementFactory,
    EnrichedRelationshipGroupFactory,
    EnrichedRootFactory,
)
from tests.helpers.selective_regen import RecordingGeneratorDiffCapturer

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot

_HASH_A = "a" * 32
_HASH_B = "b" * 32
_HASH_C = "c" * 32


def _changed_node(uuid: str) -> EnrichedDiffNode:
    return EnrichedNodeFactory.build(
        uuid=uuid,
        kind="TestDevice",
        label=uuid,
        action=DiffAction.UPDATED,
        attributes={
            EnrichedAttributeFactory.build(
                name="description", action=DiffAction.UPDATED, num_added=0, num_updated=1, num_removed=0
            )
        },
        relationships=set(),
    )


def _deleted_node(uuid: str, peer_ids: list[str]) -> EnrichedDiffNode:
    return EnrichedNodeFactory.build(
        uuid=uuid,
        kind="TestInterface",
        label=uuid,
        action=DiffAction.REMOVED,
        attributes=set(),
        relationships={
            EnrichedRelationshipGroupFactory.build(
                name="device",
                action=DiffAction.REMOVED,
                relationships={
                    EnrichedRelationshipElementFactory.build(peer_id=peer_id, action=DiffAction.REMOVED)
                    for peer_id in peer_ids
                },
            )
        },
    )


def _group(name: str, member_ids: list[str]) -> SimpleNamespace:
    peers = [SimpleNamespace(peer=SimpleNamespace(id=member_id)) for member_id in member_ids]
    return SimpleNamespace(name=SimpleNamespace(value=name), members=SimpleNamespace(peers=peers))


class _WindowDiffCoordinator(DiffCoordinator):
    """Returns a diff of the requested window that changed or deleted the given nodes, recording the nodes it was scoped to."""

    def __init__(self, changed_node_ids: list[str], deleted_node_peers: dict[str, list[str]] | None = None) -> None:
        self._changed_node_ids = changed_node_ids
        self._deleted_node_peers = deleted_node_peers or {}
        self.requested_node_uuids: list[set[str] | None] = []

    async def calculate_arbitrary_timeframe_diff(  # noqa: PLR0913, PLR0917
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        node_kinds: list[str] | None = None,
        node_uuids: set[str] | None = None,
    ) -> EnrichedDiffRoot:
        self.requested_node_uuids.append(node_uuids)
        return EnrichedRootFactory.build(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            nodes={
                _changed_node(uuid=node_id)
                for node_id in self._changed_node_ids
                if node_uuids is None or node_id in node_uuids
            }
            | {
                _deleted_node(uuid=node_id, peer_ids=peer_ids)
                for node_id, peer_ids in self._deleted_node_peers.items()
                if node_uuids is None or node_id in node_uuids
            },
        )


class _FakeClient:
    """Returns canned generator tracking groups per queried definition name and time, recording the queries."""

    def __init__(
        self,
        groups_by_name: dict[str, list[SimpleNamespace]],
        groups_at_since_by_name: dict[str, list[SimpleNamespace]] | None = None,
    ) -> None:
        self._groups_by_name = groups_by_name
        self._groups_at_since_by_name = groups_at_since_by_name or {}
        self.queries: list[tuple[str, Timestamp | None]] = []

    async def filters(  # noqa: PLR0913
        self,
        *,
        kind: Any,
        branch: str,
        at: Timestamp | None,
        name__value: str,
        partial_match: bool,
        include: list[str],
    ) -> list[SimpleNamespace]:
        self.queries.append((name__value, at))
        groups = self._groups_by_name if at is None else self._groups_at_since_by_name
        return groups.get(name__value, [])


def _capturer(client: _FakeClient, coordinator: _WindowDiffCoordinator) -> GeneratorTrackingGroupDiffCapturer:
    return GeneratorTrackingGroupDiffCapturer(
        diff_coordinator=coordinator,
        serializer=DiffSummarySerializer(),
        client=cast("InfrahubClient", client),
        branch=Branch(name="main"),
    )


def _captured_ids(diff_summary: list[NodeDiff]) -> set[str]:
    return {entry["id"] for entry in diff_summary}


async def test_capture_returns_only_the_changes_to_the_nodes_the_generators_tracked() -> None:
    # Two per-member groups for the generator (union of members), plus a decoy whose name merely contains
    # the definition name -- partial_match returns it but it is not one of this generator's groups.
    client = _FakeClient(
        {
            "set_description": [
                _group(f"set_description-{_HASH_A}", ["n1", "n2"]),
                _group(f"set_description-{_HASH_B}", ["n3"]),
                _group(f"set_descriptionEXTRA-{_HASH_C}", ["nX"]),
            ]
        }
    )
    coordinator = _WindowDiffCoordinator(changed_node_ids=["n1", "n2", "n3", "nX", "concurrent"])
    capturer = _capturer(client, coordinator)

    since = Timestamp()
    result = await capturer.capture(since=since, generator_definition_names=["set_description"])

    assert client.queries == [("set_description", None), ("set_description", since)]
    assert coordinator.requested_node_uuids == [{"n1", "n2", "n3"}]
    assert _captured_ids(result) == {"n1", "n2", "n3"}


async def test_capture_returns_every_change_in_the_window_when_no_tracking_group_resolves() -> None:
    # A generator ran but no tracking group is found: keep the window diff unscoped so a lookup miss
    # over-selects rather than dropping a consuming artifact.
    client = _FakeClient({})
    coordinator = _WindowDiffCoordinator(changed_node_ids=["n1", "concurrent"])
    capturer = _capturer(client, coordinator)

    since = Timestamp()
    result = await capturer.capture(since=since, generator_definition_names=["set_description"])

    # The full window alone would also come back if the lookup stopped happening: no query leaves no
    # ids, which widens too. The queried names separate a miss from a skipped lookup.
    assert client.queries == [("set_description", None)]
    assert coordinator.requested_node_uuids == [None]
    assert _captured_ids(result) == {"n1", "concurrent"}


async def test_capture_returns_every_change_in_the_window_when_the_tracking_group_is_empty() -> None:
    client = _FakeClient({"set_description": [_group(f"set_description-{_HASH_A}", [])]})
    coordinator = _WindowDiffCoordinator(changed_node_ids=["n1", "concurrent"])
    capturer = _capturer(client, coordinator)

    since = Timestamp()
    result = await capturer.capture(since=since, generator_definition_names=["set_description"])

    assert client.queries == [("set_description", None), ("set_description", since)]
    assert coordinator.requested_node_uuids == [None]
    assert _captured_ids(result) == {"n1", "concurrent"}


async def test_capture_ignores_groups_whose_name_is_not_a_tracking_group() -> None:
    # Only "<definition name>-<32 hex>" names count; a suffix that is not a bare hash is excluded, which
    # leaves no tracking group and keeps the window diff unscoped.
    client = _FakeClient({"set_description": [_group(f"set_description-{_HASH_A}xyz", ["n1"])]})
    coordinator = _WindowDiffCoordinator(changed_node_ids=["n1", "concurrent"])
    capturer = _capturer(client, coordinator)

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert client.queries == [("set_description", None)]
    assert coordinator.requested_node_uuids == [None]
    assert _captured_ids(result) == {"n1", "concurrent"}


async def test_capture_returns_every_change_when_any_definition_lacks_a_tracking_group() -> None:
    # One generator resolved its group, another did not; narrowing on only the resolved ids would drop
    # the unresolved generator's output, so the capture must widen instead of filtering on the aggregate.
    client = _FakeClient({"genA": [_group(f"genA-{_HASH_A}", ["n1", "n2"])]})
    coordinator = _WindowDiffCoordinator(changed_node_ids=["n1", "n2", "written-by-genB"])
    capturer = _capturer(client, coordinator)

    since = Timestamp()
    result = await capturer.capture(since=since, generator_definition_names=["genA", "genB"])

    assert client.queries == [("genA", None), ("genA", since), ("genB", None)]
    assert coordinator.requested_node_uuids == [None]
    assert _captured_ids(result) == {"n1", "n2", "written-by-genB"}


async def test_capture_includes_the_nodes_the_generators_dropped_from_their_tracking_groups() -> None:
    # The run stopped writing "dropped" and deleted it, so only the membership at the capture start lists it.
    client = _FakeClient(
        {"set_description": [_group(f"set_description-{_HASH_A}", ["n1"])]},
        groups_at_since_by_name={"set_description": [_group(f"set_description-{_HASH_A}", ["n1", "dropped"])]},
    )
    coordinator = _WindowDiffCoordinator(changed_node_ids=["n1", "dropped", "concurrent"])
    capturer = _capturer(client, coordinator)

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert coordinator.requested_node_uuids == [{"n1", "dropped"}]
    assert _captured_ids(result) == {"n1", "dropped"}


async def test_capture_returns_every_change_when_the_tracking_group_only_existed_at_the_capture_start() -> None:
    # Without a group after the run, the nodes the run wrote are unknown, so the earlier members cannot narrow.
    client = _FakeClient(
        {}, groups_at_since_by_name={"set_description": [_group(f"set_description-{_HASH_A}", ["dropped"])]}
    )
    coordinator = _WindowDiffCoordinator(changed_node_ids=["dropped", "concurrent"])
    capturer = _capturer(client, coordinator)

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert coordinator.requested_node_uuids == [None]
    assert _captured_ids(result) == {"dropped", "concurrent"}


async def test_capture_includes_the_peers_of_a_tracked_node_the_generators_deleted() -> None:
    # Deleting eth1 also changed the relationship on dev1, which the generator never tracked.
    client = _FakeClient(
        {"interfaces": [_group(f"interfaces-{_HASH_A}", ["eth0"])]},
        groups_at_since_by_name={"interfaces": [_group(f"interfaces-{_HASH_A}", ["eth0", "eth1"])]},
    )
    coordinator = _WindowDiffCoordinator(changed_node_ids=["dev1", "concurrent"], deleted_node_peers={"eth1": ["dev1"]})
    capturer = _capturer(client, coordinator)

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["interfaces"])

    assert coordinator.requested_node_uuids == [{"eth0", "eth1"}, {"eth0", "eth1", "dev1"}]
    assert _captured_ids(result) == {"eth1", "dev1"}


def _generator_run(name: str) -> RequestGeneratorDefinitionRun:
    return RequestGeneratorDefinitionRun(
        branch="main",
        generator_definition=ProposedChangeGeneratorDefinition(
            definition_id="def-1",
            definition_name=name,
            query_name="q",
            convert_query_response=False,
            class_name="C",
            file_path="gen.py",
            group_id="grp-1",
            parameters={},
            execute_in_proposed_change=False,
            execute_after_merge=True,
            query_id="q-1",
            query_payload="query {}",
            repository_id="repo-1",
        ),
    )


async def test_generator_tracking_output_captures_the_runs_generators_by_name() -> None:
    """GeneratorCascadeOutput reads the names off the runs and forwards them with since to the capturer."""
    capturer = RecordingGeneratorDiffCapturer()
    output = GeneratorCascadeOutput(capturer=capturer)
    since = Timestamp()

    captured = await output.capture(since=since, requests=[_generator_run("gen-a"), _generator_run("gen-b")])

    assert capturer.calls == [(since, ["gen-a", "gen-b"])]
    assert captured is capturer.result

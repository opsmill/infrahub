from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.selective_regen.generator_diff_capturer import GeneratorTrackingGroupDiffCapturer
from infrahub.core.timestamp import Timestamp
from tests.helpers.diff_factories import EnrichedAttributeFactory, EnrichedNodeFactory, EnrichedRootFactory

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


def _group(name: str, member_ids: list[str]) -> SimpleNamespace:
    peers = [SimpleNamespace(peer=SimpleNamespace(id=member_id)) for member_id in member_ids]
    return SimpleNamespace(name=SimpleNamespace(value=name), members=SimpleNamespace(peers=peers))


class _WindowDiffCoordinator(DiffCoordinator):
    """Returns a diff of the requested window that changed the given nodes."""

    def __init__(self, changed_node_ids: list[str]) -> None:
        self._changed_node_ids = changed_node_ids

    async def calculate_arbitrary_timeframe_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        node_kinds: list[str] | None = None,
    ) -> EnrichedDiffRoot:
        return EnrichedRootFactory.build(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            nodes={_changed_node(uuid=node_id) for node_id in self._changed_node_ids},
        )


class _FakeClient:
    """Returns canned generator tracking groups per queried definition name, recording the queries."""

    def __init__(self, groups_by_name: dict[str, list[SimpleNamespace]]) -> None:
        self._groups_by_name = groups_by_name
        self.queried_names: list[str] = []

    async def filters(
        self, *, kind: Any, branch: str, name__value: str, partial_match: bool, include: list[str]
    ) -> list[SimpleNamespace]:
        self.queried_names.append(name__value)
        return self._groups_by_name.get(name__value, [])


def _capturer(client: _FakeClient, changed_node_ids: list[str]) -> GeneratorTrackingGroupDiffCapturer:
    return GeneratorTrackingGroupDiffCapturer(
        diff_coordinator=_WindowDiffCoordinator(changed_node_ids=changed_node_ids),
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
    capturer = _capturer(client, changed_node_ids=["n1", "n2", "n3", "nX", "concurrent"])

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert _captured_ids(result) == {"n1", "n2", "n3"}


async def test_capture_returns_every_change_in_the_window_when_no_tracking_group_resolves() -> None:
    # A generator ran but no tracking group is found: keep the window diff unscoped so a lookup miss
    # over-selects rather than dropping a consuming artifact.
    client = _FakeClient({})
    capturer = _capturer(client, changed_node_ids=["n1", "concurrent"])

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    # The full window alone would also come back if the lookup stopped happening: no query leaves no
    # ids, which widens too. The queried names separate a miss from a skipped lookup.
    assert client.queried_names == ["set_description"]
    assert _captured_ids(result) == {"n1", "concurrent"}


async def test_capture_returns_every_change_in_the_window_when_the_tracking_group_is_empty() -> None:
    client = _FakeClient({"set_description": [_group(f"set_description-{_HASH_A}", [])]})
    capturer = _capturer(client, changed_node_ids=["n1", "concurrent"])

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert client.queried_names == ["set_description"]
    assert _captured_ids(result) == {"n1", "concurrent"}


async def test_capture_ignores_groups_whose_name_is_not_a_tracking_group() -> None:
    # Only "<definition name>-<32 hex>" names count; a suffix that is not a bare hash is excluded, which
    # leaves no tracking group and keeps the window diff unscoped.
    client = _FakeClient({"set_description": [_group(f"set_description-{_HASH_A}xyz", ["n1"])]})
    capturer = _capturer(client, changed_node_ids=["n1", "concurrent"])

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert client.queried_names == ["set_description"]
    assert _captured_ids(result) == {"n1", "concurrent"}


async def test_capture_returns_every_change_when_any_definition_lacks_a_tracking_group() -> None:
    # One generator resolved its group, another did not; narrowing on only the resolved ids would drop
    # the unresolved generator's output, so the capture must widen instead of filtering on the aggregate.
    client = _FakeClient({"genA": [_group(f"genA-{_HASH_A}", ["n1", "n2"])]})
    capturer = _capturer(client, changed_node_ids=["n1", "n2", "written-by-genB"])

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["genA", "genB"])

    assert client.queried_names == ["genA", "genB"]
    assert _captured_ids(result) == {"n1", "n2", "written-by-genB"}

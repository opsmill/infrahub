from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import EnrichedDiffRoot, EnrichedDiffRootMetadata, NameTrackingId, TrackingId
from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.merge.selective_regen.generator_diff_capturer import GeneratorTrackingGroupDiffCapturer
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

_HASH_A = "a" * 32
_HASH_B = "b" * 32
_HASH_C = "c" * 32


def _empty_root(branch_name: str) -> EnrichedDiffRoot:
    return EnrichedDiffRoot(
        base_branch_name=branch_name,
        diff_branch_name=branch_name,
        from_time=Timestamp(),
        to_time=Timestamp(),
        uuid="diff-uuid",
        tracking_id=NameTrackingId(name=branch_name),
    )


def _group(name: str, member_ids: list[str]) -> SimpleNamespace:
    peers = [SimpleNamespace(peer=SimpleNamespace(id=member_id)) for member_id in member_ids]
    return SimpleNamespace(name=SimpleNamespace(value=name), members=SimpleNamespace(peers=peers))


class _RecordingCoordinator(DiffCoordinator):
    def __init__(self) -> None:
        self.diff_branches: list[str] = []

    async def create_or_update_arbitrary_timeframe_diff(
        self, base_branch: Branch, diff_branch: Branch, from_time: Timestamp, to_time: Timestamp, name: str
    ) -> EnrichedDiffRootMetadata:
        self.diff_branches.append(diff_branch.name)
        return _empty_root(diff_branch.name)


class _RecordingRepository(DiffRepository):
    def __init__(self) -> None:
        self.filters_seen: list[EnrichedDiffQueryFilters | None] = []

    async def get_one(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        filters: EnrichedDiffQueryFilters | None = None,
        include_parents: bool = True,
    ) -> EnrichedDiffRoot:
        self.filters_seen.append(filters)
        return _empty_root(diff_branch_name)


class _RecordingSerializer(DiffSummarySerializer):
    def __init__(self) -> None:
        self.target_branch_names: list[str] = []

    def serialize(self, root: EnrichedDiffRoot, target_branch_name: str) -> list[NodeDiff]:
        self.target_branch_names.append(target_branch_name)
        return []


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


def _capturer(client: _FakeClient) -> tuple[GeneratorTrackingGroupDiffCapturer, _RecordingRepository]:
    repository = _RecordingRepository()
    capturer = GeneratorTrackingGroupDiffCapturer(
        diff_coordinator=_RecordingCoordinator(),
        diff_repository=repository,
        serializer=_RecordingSerializer(),
        client=cast("InfrahubClient", client),
        branch=Branch(name="main"),
    )
    return capturer, repository


async def test_capture_scopes_the_diff_read_to_the_tracked_output_nodes() -> None:
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
    capturer, repository = _capturer(client)

    result = await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert result == []
    assert repository.filters_seen == [EnrichedDiffQueryFilters(ids=["n1", "n2", "n3"])]
    assert client.queried_names == ["set_description"]


async def test_capture_widens_to_the_whole_window_when_no_tracking_group_resolves() -> None:
    # A generator ran but no tracking group is found: read the window diff unscoped so a lookup miss
    # over-selects rather than dropping a consuming artifact.
    client = _FakeClient({})
    capturer, repository = _capturer(client)

    await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert repository.filters_seen == [None]


async def test_capture_ignores_groups_whose_name_is_not_a_tracking_group() -> None:
    # Only "<definition name>-<32 hex>" names count; a suffix that is not a bare hash is excluded, which
    # leaves no ids and widens the read.
    client = _FakeClient({"set_description": [_group(f"set_description-{_HASH_A}xyz", ["n1"])]})
    capturer, repository = _capturer(client)

    await capturer.capture(since=Timestamp(), generator_definition_names=["set_description"])

    assert repository.filters_seen == [None]

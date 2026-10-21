from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import RelationshipDirection
from infrahub.core.regeneration.filtered_peers import (
    ChangedNodeIndex,
    FilteredPeerReads,
)
from infrahub.core.regeneration.models import PeerFilters, RelationshipHop, RelationshipRead
from tests.helpers.diff_summary import node_diff

from .helpers import DependentResolverCall, PeerReaderCall, RecordingDependentResolver, RecordingPeerReader

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

BRANCH = "main"
ROLE_AGGREGATE = PeerFilters(relationship_name="prefixes", filters=(("prefixes__role__value", "aggregate"),))
VRF_HOP = RelationshipHop(
    node_kind="TestVrf",
    relationship_identifier="vrf__prefix",
    relationship_direction=RelationshipDirection.OUTBOUND,
    peer_filters=ROLE_AGGREGATE,
)


def _peer_reads(
    *, diff_summary: list[NodeDiff], owners_by_peer: dict[str, set[str]], reader: RecordingPeerReader
) -> FilteredPeerReads:
    return FilteredPeerReads(
        changes=ChangedNodeIndex.from_diff(diff_summary=diff_summary, query_branch=BRANCH),
        dependents=RecordingDependentResolver(owners_by_identifier={"vrf__prefix": owners_by_peer}),
        peers=reader,
    )


@dataclass(frozen=True, kw_only=True)
class OwnersCase:
    name: str
    diff_summary: list[NodeDiff]
    peer_ids: set[str] = field(default_factory=lambda: {"p1"})
    owners_by_peer: dict[str, set[str]] = field(default_factory=lambda: {"p1": {"vrf1"}})
    passing: set[str] = field(default_factory=set)
    expected: set[str]
    expected_queried_peers: list[tuple[str, ...]]


OWNERS_CASES = [
    OwnersCase(
        name="an_added_peer_the_filters_exclude_reaches_no_owner",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", action="ADDED", field_names=["role", "vrf"])],
        expected=set(),
        expected_queried_peers=[("p1",)],
    ),
    OwnersCase(
        name="an_added_peer_the_filters_include_reaches_its_owner",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", action="ADDED", field_names=["role", "vrf"])],
        passing={"p1"},
        expected={"vrf1"},
        expected_queried_peers=[("p1",)],
    ),
    OwnersCase(
        name="a_peer_whose_filtered_field_changed_reaches_its_owner_without_a_peer_query",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", field_names=["role"])],
        expected={"vrf1"},
        expected_queried_peers=[],
    ),
    OwnersCase(
        name="a_peer_whose_other_fields_changed_is_checked_with_the_peer_query",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", field_names=["description"])],
        expected=set(),
        expected_queried_peers=[("p1",)],
    ),
    OwnersCase(
        name="a_removed_peer_reaches_its_owner_without_a_peer_query",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", action="REMOVED", field_names=["role"])],
        expected={"vrf1"},
        expected_queried_peers=[],
    ),
    # From the second hop on, the peers are the owners the previous hop returned, which the diff may not change.
    OwnersCase(
        name="peers_outside_the_diff_are_checked_with_the_peer_query",
        diff_summary=[],
        peer_ids={"p1", "p2"},
        owners_by_peer={"p1": {"vrf1"}, "p2": {"vrf2"}},
        passing={"p1"},
        expected={"vrf1"},
        expected_queried_peers=[("p1", "p2")],
    ),
    OwnersCase(
        name="a_peer_related_to_no_owner_reaches_no_owner_without_a_peer_query",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", field_names=["vrf"])],
        owners_by_peer={},
        expected=set(),
        expected_queried_peers=[],
    ),
    OwnersCase(
        name="a_peer_changed_on_another_branch_is_checked_with_the_peer_query",
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", branch="other", field_names=["role"])],
        expected=set(),
        expected_queried_peers=[("p1",)],
    ),
]


@pytest.mark.parametrize("case", OWNERS_CASES, ids=lambda case: case.name)
async def test_owners(case: OwnersCase) -> None:
    reader = RecordingPeerReader(owners_by_peer=case.owners_by_peer, passing=case.passing)
    peer_reads = _peer_reads(diff_summary=case.diff_summary, owners_by_peer=case.owners_by_peer, reader=reader)

    assert await peer_reads.owners(hop=VRF_HOP, peer_ids=case.peer_ids) == case.expected
    assert [call.peer_ids for call in reader.calls] == case.expected_queried_peers


UNFILTERED_VRF_HOP = RelationshipHop(
    node_kind="TestVrf",
    relationship_identifier="vrf__prefix",
    relationship_direction=RelationshipDirection.OUTBOUND,
    peer_filters=None,
)


async def test_a_hop_without_filters_reaches_every_current_owner_without_a_peer_query() -> None:
    reader = RecordingPeerReader(owners_by_peer={"p1": {"vrf1"}, "p2": {"vrf2"}})
    peer_reads = _peer_reads(diff_summary=[], owners_by_peer={"p1": {"vrf1"}, "p2": {"vrf2"}}, reader=reader)

    assert await peer_reads.owners(hop=UNFILTERED_VRF_HOP, peer_ids={"p1", "p2"}) == {"vrf1", "vrf2"}
    assert reader.calls == []


@pytest.mark.parametrize("peer_ids", [["p1", "p2"], ["p2", "p1"]])
async def test_peer_ids_are_passed_sorted_for_a_stable_owner_lookup(peer_ids: list[str]) -> None:
    dependents = RecordingDependentResolver(owners_by_identifier={"vrf__prefix": {}})
    peer_reads = FilteredPeerReads(
        changes=ChangedNodeIndex.from_diff(diff_summary=[], query_branch=BRANCH),
        dependents=dependents,
        peers=RecordingPeerReader(owners_by_peer={}),
    )

    await peer_reads.owners(hop=UNFILTERED_VRF_HOP, peer_ids=peer_ids)

    assert dependents.calls == [
        DependentResolverCall(
            node_kind="TestVrf",
            relationship_identifier="vrf__prefix",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("p1", "p2"),
        )
    ]


async def test_the_peer_query_receives_the_read_filters_with_list_values_as_lists() -> None:
    hop = RelationshipHop(
        node_kind="TestVrf",
        relationship_identifier="vrf__prefix",
        relationship_direction=RelationshipDirection.OUTBOUND,
        peer_filters=PeerFilters(
            relationship_name="prefixes",
            filters=(("prefixes__role__values", ("aggregate", "loopback")), ("prefixes__status__value", "active")),
        ),
    )
    reader = RecordingPeerReader(owners_by_peer={"p1": {"vrf1"}})

    await _peer_reads(diff_summary=[], owners_by_peer={"p1": {"vrf1"}}, reader=reader).owners(hop=hop, peer_ids={"p1"})

    assert reader.calls == [
        PeerReaderCall(
            owner_kind="TestVrf",
            relationship_name="prefixes",
            owner_ids=("vrf1",),
            peer_ids=("p1",),
            filters=(("prefixes__role__values", ["aggregate", "loopback"]), ("prefixes__status__value", "active")),
        )
    ]


async def test_a_read_already_queried_is_not_queried_again() -> None:
    reader = RecordingPeerReader(owners_by_peer={"p1": {"vrf1"}})
    peer_reads = _peer_reads(diff_summary=[], owners_by_peer={"p1": {"vrf1"}}, reader=reader)

    await peer_reads.owners(hop=VRF_HOP, peer_ids={"p1"})
    await peer_reads.owners(hop=VRF_HOP, peer_ids={"p1"})

    assert len(reader.calls) == 1


FILTERED_READ = RelationshipRead(
    owner_kind="TestVrf",
    relationship_name="prefixes",
    relationship_identifier="vrf__prefix",
    relationship_direction=RelationshipDirection.OUTBOUND,
    peer_kinds=frozenset({"TestPrefix"}),
    peer_filters=ROLE_AGGREGATE,
)
UNFILTERED_READ = RelationshipRead(
    owner_kind="TestVrf",
    relationship_name="prefixes",
    relationship_identifier="vrf__prefix",
    relationship_direction=RelationshipDirection.OUTBOUND,
    peer_kinds=frozenset({"TestPrefix"}),
    peer_filters=None,
)


@dataclass(frozen=True, kw_only=True)
class ReadsAnyCase:
    name: str
    read: RelationshipRead
    diff_summary: list[NodeDiff]
    peer_ids: set[str]
    owners_by_peer: dict[str, set[str]]
    passing: set[str]
    expected: bool


READS_ANY_CASES = [
    ReadsAnyCase(
        name="an_unfiltered_read_returns_any_peer",
        read=UNFILTERED_READ,
        diff_summary=[],
        peer_ids={"p1"},
        owners_by_peer={"p1": {"vrf1"}},
        passing=set(),
        expected=True,
    ),
    ReadsAnyCase(
        name="an_unfiltered_read_of_no_peer_returns_none",
        read=UNFILTERED_READ,
        diff_summary=[],
        peer_ids=set(),
        owners_by_peer={},
        passing=set(),
        expected=False,
    ),
    ReadsAnyCase(
        name="a_peer_whose_filtered_field_changed_is_assumed_to_be_returned_without_a_peer_query",
        read=FILTERED_READ,
        diff_summary=[node_diff(node_id="p1", kind="TestPrefix", field_names=["role"])],
        peer_ids={"p1"},
        owners_by_peer={"p1": {"vrf1"}},
        passing=set(),
        expected=True,
    ),
    ReadsAnyCase(
        name="a_peer_related_to_no_owner_is_assumed_to_be_returned",
        read=FILTERED_READ,
        diff_summary=[],
        peer_ids={"p1"},
        owners_by_peer={},
        passing=set(),
        expected=True,
    ),
    ReadsAnyCase(
        name="a_related_peer_passing_the_filters_is_returned",
        read=FILTERED_READ,
        diff_summary=[],
        peer_ids={"p1", "p2"},
        owners_by_peer={"p1": {"vrf1"}, "p2": {"vrf1"}},
        passing={"p2"},
        expected=True,
    ),
    ReadsAnyCase(
        name="related_peers_failing_the_filters_are_not_returned",
        read=FILTERED_READ,
        diff_summary=[],
        peer_ids={"p1", "p2"},
        owners_by_peer={"p1": {"vrf1"}, "p2": {"vrf1"}},
        passing=set(),
        expected=False,
    ),
    ReadsAnyCase(
        name="a_filtered_read_of_no_peer_returns_none",
        read=FILTERED_READ,
        diff_summary=[],
        peer_ids=set(),
        owners_by_peer={},
        passing=set(),
        expected=False,
    ),
]


@pytest.mark.parametrize("case", READS_ANY_CASES, ids=lambda case: case.name)
async def test_reads_any(case: ReadsAnyCase) -> None:
    reader = RecordingPeerReader(owners_by_peer=case.owners_by_peer, passing=case.passing)
    peer_reads = _peer_reads(diff_summary=case.diff_summary, owners_by_peer=case.owners_by_peer, reader=reader)

    assert await peer_reads.reads_any(read=case.read, peer_ids=case.peer_ids) is case.expected

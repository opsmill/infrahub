from __future__ import annotations

from infrahub.core.constants import RelationshipDirection
from infrahub.core.regeneration.filtered_peers import ChangedNodeIndex, FilteredPeerReads
from infrahub.core.regeneration.impact import ReachedMemberResolver
from infrahub.core.regeneration.impact_classifier import ReachedChange, RelationshipReachedChanges
from infrahub.core.regeneration.models import PeerFilters, ReachedPath, RelationshipHop

from .helpers import DependentResolverCall, RecordingDependentResolver, RecordingPeerReader


def _member_resolver(resolver: RecordingDependentResolver, reader: RecordingPeerReader) -> ReachedMemberResolver:
    peer_reads = FilteredPeerReads(
        changes=ChangedNodeIndex.from_diff(diff_summary=[], query_branch="main"),
        dependents=resolver,
        peers=reader,
    )
    return ReachedMemberResolver(peer_reads=peer_reads)


def _interface_filters(*filters: tuple[str, str]) -> PeerFilters:
    return PeerFilters(relationship_name="interfaces", filters=tuple(filters))


DEVICE_HOP = RelationshipHop(
    node_kind="TestDevice",
    relationship_identifier="device__interface",
    relationship_direction=RelationshipDirection.OUTBOUND,
)
INTERFACE_HOP = RelationshipHop(
    node_kind="TestInterface",
    relationship_identifier="interface__ip",
    relationship_direction=RelationshipDirection.OUTBOUND,
)


async def test_direct_member_changes_pass_through_without_a_lookup() -> None:
    resolver = RecordingDependentResolver(owners_by_identifier={})

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(direct_member_node_ids=["dev1", "dev2"], reached=[])
    )

    assert members == {"dev1", "dev2"}
    assert resolver.calls == []


async def test_an_empty_path_maps_a_changed_node_to_itself_without_a_lookup() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={"device__interface": {"dev2": {"dev1"}}},
    )

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[ReachedChange(node_ids=["dev2"], paths=(ReachedPath(hops=()), ReachedPath(hops=(DEVICE_HOP,))))],
        )
    )

    assert members == {"dev1", "dev2"}
    assert resolver.calls == [
        DependentResolverCall(
            node_kind="TestDevice",
            relationship_identifier="device__interface",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("dev2",),
        )
    ]


async def test_single_hop_resolves_the_owning_member() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={"device__interface": {"intf1": {"dev1"}}},
    )

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[ReachedChange(node_ids=["intf1"], paths=(ReachedPath(hops=(DEVICE_HOP,)),))],
        )
    )

    assert members == {"dev1"}
    assert resolver.calls == [
        DependentResolverCall(
            node_kind="TestDevice",
            relationship_identifier="device__interface",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("intf1",),
        )
    ]


async def test_multi_hop_chains_each_hop_output_into_the_next() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={
            "interface__ip": {"ip1": {"intf1", "intf2"}},
            "device__interface": {"intf1": {"dev1"}, "intf2": {"dev2"}},
        },
    )

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[ReachedChange(node_ids=["ip1"], paths=(ReachedPath(hops=(INTERFACE_HOP, DEVICE_HOP)),))],
        )
    )

    assert members == {"dev1", "dev2"}
    assert resolver.calls == [
        DependentResolverCall(
            node_kind="TestInterface",
            relationship_identifier="interface__ip",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("ip1",),
        ),
        DependentResolverCall(
            node_kind="TestDevice",
            relationship_identifier="device__interface",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("intf1", "intf2"),
        ),
    ]


async def test_multiple_paths_for_a_change_union_their_owners() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={
            "car__owner": {"p1": {"car1"}},
            "car__previous_owner": {"p1": {"car2"}},
        },
    )
    owner_hop = RelationshipHop(
        node_kind="TestCar", relationship_identifier="car__owner", relationship_direction=RelationshipDirection.OUTBOUND
    )
    previous_owner_hop = RelationshipHop(
        node_kind="TestCar",
        relationship_identifier="car__previous_owner",
        relationship_direction=RelationshipDirection.OUTBOUND,
    )

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[
                ReachedChange(
                    node_ids=["p1"],
                    paths=(ReachedPath(hops=(owner_hop,)), ReachedPath(hops=(previous_owner_hop,))),
                )
            ],
        )
    )

    assert members == {"car1", "car2"}


async def test_a_hop_resolving_to_nothing_stops_the_chain_and_contributes_no_member() -> None:
    resolver = RecordingDependentResolver(owners_by_identifier={"interface__ip": {}})

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=["dev9"],
            reached=[ReachedChange(node_ids=["ip1"], paths=(ReachedPath(hops=(INTERFACE_HOP, DEVICE_HOP)),))],
        )
    )

    assert members == {"dev9"}
    assert resolver.calls == [
        DependentResolverCall(
            node_kind="TestInterface",
            relationship_identifier="interface__ip",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("ip1",),
        )
    ]


async def test_direct_and_reached_members_union() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={"device__interface": {"intf1": {"dev1"}}},
    )

    members = await _member_resolver(resolver, RecordingPeerReader(owners_by_peer={})).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=["dev5"],
            reached=[ReachedChange(node_ids=["intf1"], paths=(ReachedPath(hops=(DEVICE_HOP,)),))],
        )
    )

    assert members == {"dev1", "dev5"}


async def test_paths_differing_only_by_their_filters_share_each_owner_lookup() -> None:
    resolver = RecordingDependentResolver(owners_by_identifier={"device__interface": {"intf1": {"dev1"}}})
    reader = RecordingPeerReader(owners_by_peer={"intf1": {"dev1"}}, passing={"intf1"})
    uplinks = RelationshipHop(
        node_kind="TestDevice",
        relationship_identifier="device__interface",
        relationship_direction=RelationshipDirection.OUTBOUND,
        peer_filters=_interface_filters(("interfaces__role__value", "uplink")),
    )
    enabled = RelationshipHop(
        node_kind="TestDevice",
        relationship_identifier="device__interface",
        relationship_direction=RelationshipDirection.OUTBOUND,
        peer_filters=_interface_filters(("interfaces__status__value", "active")),
    )

    members = await _member_resolver(resolver, reader).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[
                ReachedChange(node_ids=["intf1"], paths=(ReachedPath(hops=(uplinks,)), ReachedPath(hops=(enabled,))))
            ],
        )
    )

    assert members == {"dev1"}
    assert resolver.calls == [
        DependentResolverCall(
            node_kind="TestDevice",
            relationship_identifier="device__interface",
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=("intf1",),
        )
    ]
    assert [call.filters for call in reader.calls] == [
        (("interfaces__role__value", "uplink"),),
        (("interfaces__status__value", "active"),),
    ]

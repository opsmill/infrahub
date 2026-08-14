from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from infrahub.core.constants import RelationshipDirection
from infrahub.core.regeneration.impact import ReachedMemberResolver
from infrahub.core.regeneration.impact_classifier import ReachedChange, RelationshipReachedChanges
from infrahub.graphql.analyzer import ReachedPath, RelationshipHop


@dataclass
class RecordingDependentResolver:
    """Resolver double that records each hop and answers from a fixed per-identifier mapping.

    Keeps the calls in order so a test asserts the exact hop sequence, and returns a superset of the
    truly-related nodes exactly as the real resolver does, so the chaining is exercised end to end
    without a database.
    """

    owners_by_identifier: dict[str, dict[str, set[str]]]
    calls: list[tuple[str, str, RelationshipDirection, tuple[str, ...]]] = field(default_factory=list)

    async def resolve(
        self,
        node_kind: str,
        relationship_identifier: str,
        relationship_direction: RelationshipDirection,
        peer_uuids: list[str],
    ) -> set[str]:
        self.calls.append((node_kind, relationship_identifier, relationship_direction, tuple(peer_uuids)))
        owners: set[str] = set()
        for peer in peer_uuids:
            owners |= self.owners_by_identifier.get(relationship_identifier, {}).get(peer, set())
        return owners


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

    members = await ReachedMemberResolver(resolver=resolver).resolve(
        RelationshipReachedChanges(direct_member_node_ids=["dev1", "dev2"], reached=[])
    )

    assert members == {"dev1", "dev2"}
    assert resolver.calls == []


async def test_single_hop_resolves_the_owning_member() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={"device__interface": {"intf1": {"dev1"}}},
    )

    members = await ReachedMemberResolver(resolver=resolver).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[ReachedChange(node_ids=["intf1"], path=ReachedPath(hops=(DEVICE_HOP,)))],
        )
    )

    assert members == {"dev1"}
    assert resolver.calls == [("TestDevice", "device__interface", RelationshipDirection.OUTBOUND, ("intf1",))]


async def test_multi_hop_chains_each_hop_output_into_the_next() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={
            "interface__ip": {"ip1": {"intf1", "intf2"}},
            "device__interface": {"intf1": {"dev1"}, "intf2": {"dev2"}},
        },
    )

    members = await ReachedMemberResolver(resolver=resolver).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[ReachedChange(node_ids=["ip1"], path=ReachedPath(hops=(INTERFACE_HOP, DEVICE_HOP)))],
        )
    )

    assert members == {"dev1", "dev2"}
    assert resolver.calls == [
        ("TestInterface", "interface__ip", RelationshipDirection.OUTBOUND, ("ip1",)),
        ("TestDevice", "device__interface", RelationshipDirection.OUTBOUND, ("intf1", "intf2")),
    ]


async def test_a_hop_resolving_to_nothing_stops_the_chain_and_contributes_no_member() -> None:
    resolver = RecordingDependentResolver(owners_by_identifier={"interface__ip": {}})

    members = await ReachedMemberResolver(resolver=resolver).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=["dev9"],
            reached=[ReachedChange(node_ids=["ip1"], path=ReachedPath(hops=(INTERFACE_HOP, DEVICE_HOP)))],
        )
    )

    assert members == {"dev9"}
    assert resolver.calls == [("TestInterface", "interface__ip", RelationshipDirection.OUTBOUND, ("ip1",))]


async def test_direct_and_reached_members_union() -> None:
    resolver = RecordingDependentResolver(
        owners_by_identifier={"device__interface": {"intf1": {"dev1"}}},
    )

    members = await ReachedMemberResolver(resolver=resolver).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=["dev5"],
            reached=[ReachedChange(node_ids=["intf1"], path=ReachedPath(hops=(DEVICE_HOP,)))],
        )
    )

    assert members == {"dev1", "dev5"}


@pytest.mark.parametrize("peer_uuids", [["ip1", "ip2"], ["ip2", "ip1"]])
async def test_peer_uuids_are_passed_sorted_for_a_stable_query(peer_uuids: list[str]) -> None:
    resolver = RecordingDependentResolver(owners_by_identifier={"device__interface": {}})

    await ReachedMemberResolver(resolver=resolver).resolve(
        RelationshipReachedChanges(
            direct_member_node_ids=[],
            reached=[ReachedChange(node_ids=peer_uuids, path=ReachedPath(hops=(DEVICE_HOP,)))],
        )
    )

    assert resolver.calls[0][3] == ("ip1", "ip2")

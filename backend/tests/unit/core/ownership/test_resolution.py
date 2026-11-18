from dataclasses import dataclass

import pytest

from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    OwnerOrigin,
    OwnerState,
    ResolvedOwnership,
    StoredNodeOwnership,
    StoredOwnerState,
)
from infrahub.core.ownership.resolution import (
    resolve_field_ownership,
    resolve_node_ownership,
    resolve_target_ownership,
)

LINEAGE_IDS = ("interface", "device", "site")


@dataclass
class NodeOwnershipTestCase:
    name: str
    owner_ids: tuple[tuple[str, ...] | None, ...]
    """The stored owners of the node, then of each parent above it. None is inherit, an empty tuple is "no owner"."""

    expected: ResolvedOwnership


NODE_OWNERSHIP_TEST_CASES: list[NodeOwnershipTestCase] = [
    NodeOwnershipTestCase(
        name="own_owners_stop_the_walk",
        owner_ids=(("dc-emea",), ("network-emea",), ("security",)),
        expected=ResolvedOwnership(
            state=OwnerState.OWNERS, owner_ids=("dc-emea",), origin=OwnerOrigin.SELF, origin_node_id="interface"
        ),
    ),
    NodeOwnershipTestCase(
        name="owners_of_the_nearest_parent_with_owners_apply",
        owner_ids=(None, None, ("security",)),
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PARENT, origin_node_id="site"
        ),
    ),
    NodeOwnershipTestCase(
        name="owners_of_a_parent_stop_the_walk",
        owner_ids=(None, ("network-emea",), ("security",)),
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("network-emea",), origin=OwnerOrigin.PARENT, origin_node_id="device"
        ),
    ),
    NodeOwnershipTestCase(
        name="no_owner_of_a_parent_stops_the_walk",
        owner_ids=(None, (), ("security",)),
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=(), origin=OwnerOrigin.PARENT, origin_node_id="device"
        ),
    ),
    NodeOwnershipTestCase(
        name="parents_without_state_give_nothing",
        owner_ids=(None, None, None),
        expected=ResolvedOwnership(state=OwnerState.INHERIT, owner_ids=(), origin=None, origin_node_id=None),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NODE_OWNERSHIP_TEST_CASES])
def test_resolve_node_ownership(test_case: NodeOwnershipTestCase) -> None:
    lineage = [
        StoredNodeOwnership(
            node_id=node_id,
            kind="TestNode",
            holders={} if owner_ids is None else {NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids)},
        )
        for node_id, owner_ids in zip(LINEAGE_IDS, test_case.owner_ids, strict=False)
    ]

    assert resolve_node_ownership(lineage=lineage, profiles={}) == test_case.expected


def _node(
    node_id: str,
    owner_ids: tuple[str, ...] | None = None,
    template_id: str | None = None,
    profiles: tuple[tuple[str, int | None], ...] = (),
) -> StoredNodeOwnership:
    holders = {} if owner_ids is None else {NODE_HOLDER: StoredOwnerState(owner_ids=owner_ids, template_id=template_id)}
    return StoredNodeOwnership(node_id=node_id, kind="TestNode", holders=holders, profiles=profiles)


def _profile(node_id: str, given_owner_ids: tuple[str, ...] | None) -> StoredNodeOwnership:
    holders = {} if given_owner_ids is None else {NODE_TARGET_HOLDER: StoredOwnerState(owner_ids=given_owner_ids)}
    return StoredNodeOwnership(node_id=node_id, kind="ProfileTestNode", holders=holders)


@dataclass
class OwnerOrderTestCase:
    name: str
    lineage: list[StoredNodeOwnership]
    """The node, then each parent above it."""

    profiles: list[StoredNodeOwnership]
    expected: ResolvedOwnership


OWNER_ORDER_TEST_CASES: list[OwnerOrderTestCase] = [
    OwnerOrderTestCase(
        name="own_owners_win_over_a_profile_and_the_parent",
        lineage=[
            _node(node_id="device", owner_ids=("dc-emea",), profiles=(("profile-a", 10),)),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=("security",))],
        expected=ResolvedOwnership(
            state=OwnerState.OWNERS, owner_ids=("dc-emea",), origin=OwnerOrigin.SELF, origin_node_id="device"
        ),
    ),
    OwnerOrderTestCase(
        name="own_no_owner_wins_over_a_profile_and_the_parent",
        lineage=[
            _node(node_id="device", owner_ids=(), profiles=(("profile-a", 10),)),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=("security",))],
        expected=ResolvedOwnership(
            state=OwnerState.NO_OWNER, owner_ids=(), origin=OwnerOrigin.SELF, origin_node_id="device"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_wins_over_a_template_copy_and_the_parent",
        lineage=[
            _node(node_id="device", owner_ids=("dc-emea",), template_id="template", profiles=(("profile-a", 10),)),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=("security",))],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PROFILE, origin_node_id="profile-a"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_with_the_lowest_priority_number_wins",
        lineage=[_node(node_id="device", profiles=(("profile-a", 20), ("profile-b", 10), ("profile-c", 30)))],
        profiles=[
            _profile(node_id="profile-a", given_owner_ids=("dc-emea",)),
            _profile(node_id="profile-b", given_owner_ids=("security",)),
            _profile(node_id="profile-c", given_owner_ids=("network-emea",)),
        ],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PROFILE, origin_node_id="profile-b"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_without_priority_comes_after_the_profiles_with_a_priority",
        lineage=[_node(node_id="device", profiles=(("profile-a", None), ("profile-b", 1000)))],
        profiles=[
            _profile(node_id="profile-a", given_owner_ids=("dc-emea",)),
            _profile(node_id="profile-b", given_owner_ids=("security",)),
        ],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PROFILE, origin_node_id="profile-b"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_with_the_lowest_id_wins_at_the_same_priority",
        lineage=[_node(node_id="device", profiles=(("profile-b", 10), ("profile-a", 10)))],
        profiles=[
            _profile(node_id="profile-a", given_owner_ids=("dc-emea",)),
            _profile(node_id="profile-b", given_owner_ids=("security",)),
        ],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("dc-emea",), origin=OwnerOrigin.PROFILE, origin_node_id="profile-a"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_that_gives_nothing_leaves_the_next_profile",
        lineage=[_node(node_id="device", profiles=(("profile-a", 10), ("profile-b", 20)))],
        profiles=[
            _profile(node_id="profile-a", given_owner_ids=None),
            _profile(node_id="profile-b", given_owner_ids=("security",)),
        ],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PROFILE, origin_node_id="profile-b"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_that_gives_no_owner_wins_over_the_parent",
        lineage=[
            _node(node_id="device", profiles=(("profile-a", 10),)),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=())],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=(), origin=OwnerOrigin.PROFILE, origin_node_id="profile-a"
        ),
    ),
    OwnerOrderTestCase(
        name="template_copy_wins_over_the_parent",
        lineage=[
            _node(node_id="device", owner_ids=("dc-emea",), template_id="template", profiles=(("profile-a", 10),)),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=None)],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("dc-emea",), origin=OwnerOrigin.TEMPLATE, origin_node_id="template"
        ),
    ),
    OwnerOrderTestCase(
        name="parent_applies_when_no_profile_gives_owners",
        lineage=[
            _node(node_id="device", profiles=(("profile-a", 10), ("profile-removed", 20))),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=None)],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("network-emea",), origin=OwnerOrigin.PARENT, origin_node_id="rack"
        ),
    ),
    OwnerOrderTestCase(
        name="profile_of_the_parent_applies_with_the_parent_as_origin",
        lineage=[
            _node(node_id="interface"),
            _node(node_id="device", profiles=(("profile-a", 10),)),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[_profile(node_id="profile-a", given_owner_ids=("security",))],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PARENT, origin_node_id="device"
        ),
    ),
    OwnerOrderTestCase(
        name="template_copy_of_the_parent_applies_with_the_parent_as_origin",
        lineage=[
            _node(node_id="interface"),
            _node(node_id="device", owner_ids=("dc-emea",), template_id="template"),
            _node(node_id="rack", owner_ids=("network-emea",)),
        ],
        profiles=[],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("dc-emea",), origin=OwnerOrigin.PARENT, origin_node_id="device"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_ORDER_TEST_CASES])
def test_resolve_node_ownership_applies_the_order_of_the_owner_sources(test_case: OwnerOrderTestCase) -> None:
    profiles = {profile.node_id: profile for profile in test_case.profiles}

    assert resolve_node_ownership(lineage=test_case.lineage, profiles=profiles) == test_case.expected


FIELD = HolderKey(kind=HolderKind.FIELD_SET, identifier="device__ip_addresses", direction="bidirectional")
GIVEN_FIELD = HolderKey(kind=HolderKind.TARGET_SET, identifier="device__ip_addresses", direction="bidirectional")
OTHER_GIVEN_FIELD = HolderKey(kind=HolderKind.TARGET_SET, attribute="description")
NODE_OWNERSHIP = ResolvedOwnership(
    state=OwnerState.INHERIT, owner_ids=("server-team",), origin=OwnerOrigin.PARENT, origin_node_id="rack"
)
NO_NODE_OWNERSHIP = ResolvedOwnership(state=OwnerState.INHERIT, owner_ids=(), origin=None, origin_node_id=None)


def _server(
    field: StoredOwnerState | None = None, profiles: tuple[tuple[str, int | None], ...] = ()
) -> StoredNodeOwnership:
    """Return a server whose own owners are of no use to its fields: a field takes the owners that apply to the node."""
    holders = {NODE_HOLDER: StoredOwnerState(owner_ids=("unused",))} | ({FIELD: field} if field else {})
    return StoredNodeOwnership(node_id="server", kind="TestServer", holders=holders, profiles=profiles)


def _field_profile(node_id: str, holder: HolderKey, owner_ids: tuple[str, ...]) -> StoredNodeOwnership:
    return StoredNodeOwnership(
        node_id=node_id, kind="ProfileTestServer", holders={holder: StoredOwnerState(owner_ids=owner_ids)}
    )


@dataclass
class FieldOwnershipTestCase:
    name: str
    node: StoredNodeOwnership
    profiles: list[StoredNodeOwnership]
    expected: ResolvedOwnership
    node_ownership: ResolvedOwnership = NODE_OWNERSHIP


FIELD_OWNERSHIP_TEST_CASES: list[FieldOwnershipTestCase] = [
    FieldOwnershipTestCase(
        name="field_without_state_takes_the_owners_that_apply_to_its_node",
        node=_server(),
        profiles=[],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("server-team",), origin=OwnerOrigin.OBJECT, origin_node_id="server"
        ),
    ),
    FieldOwnershipTestCase(
        name="field_of_a_node_without_owner_has_no_origin",
        node=_server(),
        profiles=[],
        node_ownership=NO_NODE_OWNERSHIP,
        expected=NO_NODE_OWNERSHIP,
    ),
    FieldOwnershipTestCase(
        name="own_owners_win_over_a_profile_and_the_node",
        node=_server(field=StoredOwnerState(owner_ids=("network-team",)), profiles=(("profile-a", 10),)),
        profiles=[_field_profile(node_id="profile-a", holder=GIVEN_FIELD, owner_ids=("security",))],
        expected=ResolvedOwnership(
            state=OwnerState.OWNERS, owner_ids=("network-team",), origin=OwnerOrigin.SELF, origin_node_id="server"
        ),
    ),
    FieldOwnershipTestCase(
        name="own_no_owner_wins_over_a_profile_and_the_node",
        node=_server(field=StoredOwnerState(owner_ids=()), profiles=(("profile-a", 10),)),
        profiles=[_field_profile(node_id="profile-a", holder=GIVEN_FIELD, owner_ids=("security",))],
        expected=ResolvedOwnership(
            state=OwnerState.NO_OWNER, owner_ids=(), origin=OwnerOrigin.SELF, origin_node_id="server"
        ),
    ),
    FieldOwnershipTestCase(
        name="profile_with_the_lowest_priority_number_wins_over_the_template_copy",
        node=_server(
            field=StoredOwnerState(owner_ids=("network-team",), template_id="template"),
            profiles=(("profile-a", 20), ("profile-b", 10)),
        ),
        profiles=[
            _field_profile(node_id="profile-a", holder=GIVEN_FIELD, owner_ids=("dc-emea",)),
            _field_profile(node_id="profile-b", holder=GIVEN_FIELD, owner_ids=("security",)),
        ],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("security",), origin=OwnerOrigin.PROFILE, origin_node_id="profile-b"
        ),
    ),
    FieldOwnershipTestCase(
        name="profile_that_gives_owners_to_the_node_or_to_another_field_gives_nothing_to_the_field",
        node=_server(profiles=(("profile-a", 10), ("profile-b", 20))),
        profiles=[
            _field_profile(node_id="profile-a", holder=NODE_TARGET_HOLDER, owner_ids=("dc-emea",)),
            _field_profile(node_id="profile-b", holder=OTHER_GIVEN_FIELD, owner_ids=("security",)),
        ],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT, owner_ids=("server-team",), origin=OwnerOrigin.OBJECT, origin_node_id="server"
        ),
    ),
    FieldOwnershipTestCase(
        name="template_copy_wins_over_the_node",
        node=_server(field=StoredOwnerState(owner_ids=("network-team",), template_id="template")),
        profiles=[],
        expected=ResolvedOwnership(
            state=OwnerState.INHERIT,
            owner_ids=("network-team",),
            origin=OwnerOrigin.TEMPLATE,
            origin_node_id="template",
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FIELD_OWNERSHIP_TEST_CASES])
def test_resolve_field_ownership_applies_the_order_of_the_owner_sources(test_case: FieldOwnershipTestCase) -> None:
    profiles = {profile.node_id: profile for profile in test_case.profiles}

    resolved = resolve_field_ownership(
        node=test_case.node, holder=FIELD, profiles=profiles, node_ownership=test_case.node_ownership
    )

    assert resolved == test_case.expected


def test_resolve_target_ownership_gives_the_owners_that_a_profile_gives_to_one_field() -> None:
    profile = _field_profile(node_id="profile-a", holder=GIVEN_FIELD, owner_ids=("security",))

    assert resolve_target_ownership(node=profile, holder=FIELD) == ResolvedOwnership(
        state=OwnerState.OWNERS, owner_ids=("security",), origin=OwnerOrigin.SELF, origin_node_id="profile-a"
    )
    assert resolve_target_ownership(node=profile) == ResolvedOwnership(
        state=OwnerState.INHERIT, owner_ids=(), origin=None, origin_node_id=None
    )

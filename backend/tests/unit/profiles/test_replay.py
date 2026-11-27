from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.changelog.models import (
    AttributeChangelog,
    NodeChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.constants import DiffAction
from infrahub.profiles.replay import (
    LinkedNodeState,
    ProfileValueSelector,
    RefreshAllNodes,
    ReplayedProfile,
    find_replayed_profiles,
)

if TYPE_CHECKING:
    from uuid import UUID

PROFILE_KIND = "ProfileTestServer"
TRIGGER_FIELDS = {PROFILE_KIND: ["profile_priority", "rack", "role", "room"]}


def _changelog(
    node_id: str,
    kind: str = PROFILE_KIND,
    attributes: dict[str, Any] | None = None,
    relationships: list[str] | None = None,
) -> NodeChangelog:
    return NodeChangelog(
        node_id=node_id,
        node_kind=kind,
        display_label=node_id,
        attributes={
            name: AttributeChangelog(name=name, value=value, kind="Text") for name, value in (attributes or {}).items()
        },
        relationships={
            name: RelationshipCardinalityOneChangelog(name=name, peer_id="peer-1") for name in relationships or []
        },
    )


@dataclass
class FindTestCase:
    name: str
    changelogs: list[tuple[DiffAction, NodeChangelog]]
    expected: list[ReplayedProfile] = field(default_factory=list)


FIND_TEST_CASES = [
    FindTestCase(
        name="attribute_change",
        changelogs=[(DiffAction.UPDATED, _changelog("profile-1", attributes={"role": "role-2", "rack": None}))],
        expected=[ReplayedProfile(profile_id="profile-1", profile_kind=PROFILE_KIND, attribute_names=["rack", "role"])],
    ),
    FindTestCase(
        name="priority_change",
        changelogs=[
            (DiffAction.UPDATED, _changelog("profile-1", attributes={"role": "role-2", "profile_priority": 5}))
        ],
        expected=[ReplayedProfile(profile_id="profile-1", profile_kind=PROFILE_KIND, attribute_names=None)],
    ),
    FindTestCase(
        name="relationship_change",
        changelogs=[
            (DiffAction.UPDATED, _changelog("profile-1", attributes={"role": "role-2"}, relationships=["room"]))
        ],
        expected=[ReplayedProfile(profile_id="profile-1", profile_kind=PROFILE_KIND, attribute_names=None)],
    ),
    FindTestCase(
        name="profile_replayed_from_both_branches",
        changelogs=[
            (DiffAction.UPDATED, _changelog("profile-1", attributes={"role": "role-2"})),
            (DiffAction.UPDATED, _changelog("profile-1", attributes={"rack": "rack-2"})),
        ],
        expected=[ReplayedProfile(profile_id="profile-1", profile_kind=PROFILE_KIND, attribute_names=["rack", "role"])],
    ),
    FindTestCase(
        name="profile_replayed_from_both_branches_with_a_priority_change",
        changelogs=[
            (DiffAction.UPDATED, _changelog("profile-1", attributes={"profile_priority": 5})),
            (DiffAction.UPDATED, _changelog("profile-1", attributes={"role": "role-2"})),
        ],
        expected=[ReplayedProfile(profile_id="profile-1", profile_kind=PROFILE_KIND, attribute_names=None)],
    ),
    FindTestCase(
        name="change_outside_the_refresh_fields",
        changelogs=[(DiffAction.UPDATED, _changelog("profile-1", attributes={"profile_name": "renamed"}))],
    ),
    FindTestCase(
        name="created_or_deleted_profile",
        changelogs=[
            (DiffAction.ADDED, _changelog("profile-1", attributes={"role": "role-2"})),
            (DiffAction.REMOVED, _changelog("profile-2", attributes={"role": "role-2"})),
        ],
    ),
    FindTestCase(
        name="node_of_another_kind",
        changelogs=[(DiffAction.UPDATED, _changelog("server-1", kind="TestServer", attributes={"role": "role-2"}))],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FIND_TEST_CASES])
def test_find_replayed_profiles(test_case: FindTestCase) -> None:
    assert find_replayed_profiles(changelogs=test_case.changelogs, trigger_fields=TRIGGER_FIELDS) == test_case.expected


PROFILE_ID = "profile-1"
PROFILE_VALUES = {"rack": "rack-1", "role": "role-2"}


class FakeProfileValueReader:
    """Answers with the profile values and the linked nodes that the test states up front."""

    def __init__(self, profile_values: dict[str, Any] | None, nodes: dict[str, LinkedNodeState]) -> None:
        self.profile_values = profile_values
        self.nodes = nodes

    async def get_profile_values(
        self, branch_name: str, profile_id: str, attribute_names: list[str]
    ) -> dict[str, Any] | None:
        return self.profile_values

    async def get_linked_nodes(
        self, branch_name: str, node_ids: list[str], attribute_names: list[str]
    ) -> dict[str, LinkedNodeState]:
        return {node_id: self.nodes[node_id] for node_id in node_ids if node_id in self.nodes}


def _linked_node(
    profile_ids: list[str] | None = None,
    values: dict[str, Any] | None = None,
    source_ids: dict[str, str | UUID | None] | None = None,
) -> LinkedNodeState:
    return LinkedNodeState(
        values=values or PROFILE_VALUES,
        source_ids=source_ids or dict.fromkeys(PROFILE_VALUES, PROFILE_ID),
        profile_ids=profile_ids or [PROFILE_ID],
    )


@dataclass
class SelectTestCase:
    name: str
    node: LinkedNodeState | None
    expected: list[str]


SELECT_TEST_CASES: list[SelectTestCase] = [
    SelectTestCase(name="holds_each_value_from_its_only_profile", node=_linked_node(), expected=[]),
    SelectTestCase(
        name="has_another_profile", node=_linked_node(profile_ids=[PROFILE_ID, "profile-2"]), expected=["node-1"]
    ),
    SelectTestCase(
        name="equal_value_from_another_source",
        node=_linked_node(source_ids={"rack": PROFILE_ID, "role": "profile-2"}),
        expected=["node-1"],
    ),
    SelectTestCase(
        name="different_value", node=_linked_node(values={"rack": "rack-1", "role": "role-1"}), expected=["node-1"]
    ),
    SelectTestCase(name="deleted_node", node=None, expected=["node-1"]),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in SELECT_TEST_CASES])
async def test_profile_value_filter_select(test_case: SelectTestCase) -> None:
    reader = FakeProfileValueReader(
        profile_values=PROFILE_VALUES, nodes={"node-1": test_case.node} if test_case.node else {}
    )
    node_filter = await ProfileValueSelector(reader=reader).prepare(
        branch_name="main", profile_id=PROFILE_ID, attribute_names=sorted(PROFILE_VALUES)
    )

    assert node_filter is not None
    assert await node_filter.select(["node-1"]) == test_case.expected


async def test_profile_value_selector_prepare_without_profile() -> None:
    reader = FakeProfileValueReader(profile_values=None, nodes={"node-1": _linked_node()})

    assert (
        await ProfileValueSelector(reader=reader).prepare(
            branch_name="main", profile_id=PROFILE_ID, attribute_names=sorted(PROFILE_VALUES)
        )
        is None
    )


async def test_refresh_all_nodes_select_keeps_the_page() -> None:
    assert await RefreshAllNodes().select(["node-1", "node-2"]) == ["node-1", "node-2"]

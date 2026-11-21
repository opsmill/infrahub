from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.core.changelog.models import (
    AttributeChangelog,
    NodeChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.constants import DiffAction
from infrahub.profiles.replay import ReplayedProfile, find_replayed_profiles

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

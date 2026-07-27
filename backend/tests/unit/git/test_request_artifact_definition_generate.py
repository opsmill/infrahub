from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.git.models import RequestArtifactDefinitionGenerate

EXISTING_MEMBER = "member-with-artifact"
NEW_MEMBER = "member-without-artifact"
EXISTING_ARTIFACT = "artifact-1"


def _request(*, members: list[str] | None = None, limit: list[str] | None = None) -> RequestArtifactDefinitionGenerate:
    return RequestArtifactDefinitionGenerate(
        artifact_definition_id="ad1",
        artifact_definition_name="device-config",
        branch="main",
        members=members or [],
        limit=limit or [],
    )


@dataclass(frozen=True, kw_only=True)
class SelectCase:
    name: str
    members: list[str]
    limit: list[str]
    member_id: str
    artifact_id: str | None
    expected: bool


SELECT_CASES = [
    SelectCase(
        name="no_filters_selects_everyone",
        members=[],
        limit=[],
        member_id=NEW_MEMBER,
        artifact_id=None,
        expected=True,
    ),
    SelectCase(
        name="members_selects_listed_new_member",
        members=[EXISTING_MEMBER, NEW_MEMBER],
        limit=[],
        member_id=NEW_MEMBER,
        artifact_id=None,
        expected=True,
    ),
    SelectCase(
        name="members_selects_listed_existing_member",
        members=[EXISTING_MEMBER, NEW_MEMBER],
        limit=[],
        member_id=EXISTING_MEMBER,
        artifact_id=EXISTING_ARTIFACT,
        expected=True,
    ),
    SelectCase(
        name="members_skips_unlisted_member",
        members=[EXISTING_MEMBER],
        limit=[],
        member_id=NEW_MEMBER,
        artifact_id=None,
        expected=False,
    ),
    SelectCase(
        name="limit_trap_skips_new_member_without_artifact",
        members=[],
        limit=[EXISTING_ARTIFACT],
        member_id=NEW_MEMBER,
        artifact_id=None,
        expected=False,
    ),
    SelectCase(
        name="limit_selects_member_with_listed_artifact",
        members=[],
        limit=[EXISTING_ARTIFACT],
        member_id=EXISTING_MEMBER,
        artifact_id=EXISTING_ARTIFACT,
        expected=True,
    ),
]


@pytest.mark.parametrize("case", SELECT_CASES, ids=lambda case: case.name)
def test_selects_member(case: SelectCase) -> None:
    request = _request(members=case.members, limit=case.limit)
    assert request.selects_member(member_id=case.member_id, artifact_id=case.artifact_id) is case.expected


@dataclass(frozen=True, kw_only=True)
class EveryMemberCase:
    name: str
    members: list[str]
    limit: list[str]
    expected: bool


EVERY_MEMBER_CASES = [
    EveryMemberCase(name="no_filter_evaluates_every_member", members=[], limit=[], expected=True),
    EveryMemberCase(name="limit_filter_does_not", members=[], limit=[EXISTING_ARTIFACT], expected=False),
    EveryMemberCase(name="members_filter_does_not", members=[EXISTING_MEMBER], limit=[], expected=False),
    EveryMemberCase(name="both_filters_do_not", members=[EXISTING_MEMBER], limit=[EXISTING_ARTIFACT], expected=False),
]


@pytest.mark.parametrize("case", EVERY_MEMBER_CASES, ids=lambda case: case.name)
def test_evaluates_every_member(case: EveryMemberCase) -> None:
    """Only an unfiltered pass looks at every member.

    Deleting an artifact whose target left the group is sound only when the pass considered the
    whole group; a pass narrowed by either filter has no standing to conclude anything about the
    members it never examined. Reading the ``limit`` filter alone would call a ``members``-scoped
    pass complete, because such a pass leaves ``limit`` empty.
    """
    assert _request(members=case.members, limit=case.limit).evaluates_every_member is case.expected


def test_members_filter_processes_a_new_member_the_limit_filter_would_drop() -> None:
    # The safety-critical contrast: a group with one existing-artifact member and one artifact-less
    # new member. members=[both] processes both; the limit filter alone would silently drop the new
    # member because it keys on the (absent) artifact id.
    both = _request(members=[EXISTING_MEMBER, NEW_MEMBER])
    assert both.selects_member(member_id=EXISTING_MEMBER, artifact_id=EXISTING_ARTIFACT) is True
    assert both.selects_member(member_id=NEW_MEMBER, artifact_id=None) is True

    limit_only = _request(limit=[EXISTING_ARTIFACT])
    assert limit_only.selects_member(member_id=NEW_MEMBER, artifact_id=None) is False

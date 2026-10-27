from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.schema import NodeSchemaAPI, RelationshipSchemaAPI
from infrahub_sdk.schema.main import RelationshipCardinality, RelationshipKind

from infrahub.core.regeneration.members import (
    ArtifactCheckRecord,
    ArtifactRecheckPlan,
    map_subscriber_ids_by_member,
    plan_artifact_recheck,
)
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

DEFINITION_NAME = "artifact-def"

SUBSCRIBER_SCHEMA = NodeSchemaAPI(
    name="Subscriber",
    namespace="Test",
    relationships=[
        RelationshipSchemaAPI(
            name="object",
            peer="TestMember",
            kind=RelationshipKind.ATTRIBUTE,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)
MEMBER_SCHEMA = NodeSchemaAPI(name="Member", namespace="Test")


def _member(client: InfrahubClient, *, member_id: str | None) -> InfrahubNode:
    return InfrahubNode(client=client, schema=MEMBER_SCHEMA, data={"__typename": "TestMember", "id": member_id})


def _subscriber(client: InfrahubClient, *, subscriber_id: str, object_data: object) -> InfrahubNode:
    return InfrahubNode(
        client=client,
        schema=SUBSCRIBER_SCHEMA,
        data={"id": subscriber_id, "__typename": "TestSubscriber", "object": object_data},
    )


def test_map_subscriber_ids_by_member_resolves_members_through_the_object_peer(
    client: InfrahubClient, log: logging.Logger
) -> None:
    """Each resolvable subscriber maps its member id (read from the object peer) to its own id."""
    subscribers = [
        _subscriber(client, subscriber_id="sub-1", object_data=_member(client, member_id="member-1")),
        _subscriber(client, subscriber_id="sub-2", object_data=_member(client, member_id="member-2")),
    ]

    result = map_subscriber_ids_by_member(existing_subscribers=subscribers, definition_name=DEFINITION_NAME, log=log)

    assert result == {"member-1": "sub-1", "member-2": "sub-2"}


@dataclass(frozen=True, kw_only=True)
class UnresolvablePeerCase:
    name: str
    object_data: dict[str, object] = field(default_factory=dict)


UNRESOLVABLE_PEER_CASES = [
    # relationship carries no identifier at all -> peer lookup raises ValueError
    UnresolvablePeerCase(name="no-identifier", object_data={"node": {"__typename": "TestMember"}}),
    # relationship references a peer absent from the client store -> raises NodeNotFoundError
    UnresolvablePeerCase(name="store-miss", object_data={"node": {"id": "gone", "__typename": "TestMember"}}),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in UNRESOLVABLE_PEER_CASES])
def test_map_subscriber_ids_by_member_skips_and_warns_when_object_peer_unresolvable(
    case: UnresolvablePeerCase,
    client: InfrahubClient,
    log: logging.Logger,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A subscriber whose object peer cannot be resolved is skipped with a warning, not fatal.

    The mapper must keep mapping the remaining subscribers rather than letting the
    unresolvable-peer exception escape and abort the caller.
    """
    subscribers = [
        _subscriber(client, subscriber_id="orphan", object_data=case.object_data),
        _subscriber(client, subscriber_id="sub-live", object_data=_member(client, member_id="member-live")),
    ]

    with caplog.at_level(logging.WARNING):
        result = map_subscriber_ids_by_member(
            existing_subscribers=subscribers, definition_name=DEFINITION_NAME, log=log
        )

    assert result == {"member-live": "sub-live"}
    assert caplog.messages == [
        "Skipping orphan subscriber orphan for definition artifact-def: object peer unresolvable"
    ]


def test_map_subscriber_ids_by_member_skips_subscriber_whose_peer_has_no_id(
    client: InfrahubClient, log: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """A resolvable peer that carries no id is skipped silently rather than mapped under ``None``."""
    subscribers = [
        _subscriber(client, subscriber_id="sub-empty", object_data=_member(client, member_id=None)),
        _subscriber(client, subscriber_id="sub-live", object_data=_member(client, member_id="member-live")),
    ]

    with caplog.at_level(logging.WARNING):
        result = map_subscriber_ids_by_member(
            existing_subscribers=subscribers, definition_name=DEFINITION_NAME, log=log
        )

    assert result == {"member-live": "sub-live"}
    assert not caplog.text


BRANCHED_FROM = Timestamp("2026-10-01T10:00:00Z")
PREVIOUS_RUN = Timestamp("2026-10-01T12:00:00Z")


def _check(artifact_id: str, checked_at: str, failed: bool = False) -> ArtifactCheckRecord:
    return ArtifactCheckRecord(artifact_id=artifact_id, checked_at=Timestamp(checked_at), failed=failed)


@dataclass(frozen=True, kw_only=True)
class RecheckCase:
    name: str
    artifact_ids: list[str]
    checks: list[ArtifactCheckRecord]
    previous_run_started_at: Timestamp | None
    expected: ArtifactRecheckPlan


RECHECK_CASES = [
    RecheckCase(
        name="never-checked-counts-as-checked-at-the-branch-point",
        artifact_ids=["art-1"],
        checks=[],
        previous_run_started_at=None,
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset(),
            recent_since=None,
            recent_latest=None,
            older_ids=frozenset({"art-1"}),
            older_since=BRANCHED_FROM,
            older_latest=BRANCHED_FROM,
            always_ids=frozenset(),
        ),
    ),
    RecheckCase(
        name="checked-during-the-previous-run-is-recent",
        artifact_ids=["art-1"],
        checks=[_check("art-1", "2026-10-01T12:00:05Z")],
        previous_run_started_at=PREVIOUS_RUN,
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset({"art-1"}),
            recent_since=PREVIOUS_RUN,
            recent_latest=Timestamp("2026-10-01T12:00:05Z"),
            older_ids=frozenset(),
            older_since=None,
            older_latest=None,
            always_ids=frozenset(),
        ),
    ),
    RecheckCase(
        name="checked-before-the-previous-run-is-older",
        artifact_ids=["art-1", "art-2"],
        checks=[_check("art-1", "2026-10-01T11:00:00Z"), _check("art-2", "2026-10-01T11:30:00Z")],
        previous_run_started_at=PREVIOUS_RUN,
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset(),
            recent_since=None,
            recent_latest=None,
            older_ids=frozenset({"art-1", "art-2"}),
            older_since=Timestamp("2026-10-01T11:00:00Z"),
            older_latest=Timestamp("2026-10-01T11:30:00Z"),
            always_ids=frozenset(),
        ),
    ),
    RecheckCase(
        name="latest-check-wins",
        artifact_ids=["art-1"],
        checks=[_check("art-1", "2026-10-01T11:00:00Z"), _check("art-1", "2026-10-01T12:00:05Z")],
        previous_run_started_at=PREVIOUS_RUN,
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset({"art-1"}),
            recent_since=PREVIOUS_RUN,
            recent_latest=Timestamp("2026-10-01T12:00:05Z"),
            older_ids=frozenset(),
            older_since=None,
            older_latest=None,
            always_ids=frozenset(),
        ),
    ),
    RecheckCase(
        name="failed-last-check-is-always-checked",
        artifact_ids=["art-1"],
        checks=[_check("art-1", "2026-10-01T12:00:05Z", failed=True)],
        previous_run_started_at=PREVIOUS_RUN,
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset(),
            recent_since=None,
            recent_latest=None,
            older_ids=frozenset(),
            older_since=None,
            older_latest=None,
            always_ids=frozenset({"art-1"}),
        ),
    ),
    RecheckCase(
        name="checked-before-the-branch-point-is-always-checked",
        artifact_ids=["art-1"],
        checks=[_check("art-1", "2026-10-01T09:00:00Z")],
        previous_run_started_at=Timestamp("2026-10-01T08:59:00Z"),
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset(),
            recent_since=None,
            recent_latest=None,
            older_ids=frozenset(),
            older_since=None,
            older_latest=None,
            always_ids=frozenset({"art-1"}),
        ),
    ),
    RecheckCase(
        name="checks-of-other-artifacts-are-ignored",
        artifact_ids=["art-1"],
        checks=[_check("art-other", "2026-10-01T12:00:05Z", failed=True)],
        previous_run_started_at=PREVIOUS_RUN,
        expected=ArtifactRecheckPlan(
            recent_ids=frozenset(),
            recent_since=None,
            recent_latest=None,
            older_ids=frozenset({"art-1"}),
            older_since=BRANCHED_FROM,
            older_latest=BRANCHED_FROM,
            always_ids=frozenset(),
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in RECHECK_CASES])
def test_plan_artifact_recheck(case: RecheckCase) -> None:
    """Artifacts are grouped by their last check, and failed or pre-rebase checks are always checked again."""
    plan = plan_artifact_recheck(
        artifact_ids=case.artifact_ids,
        check_records=case.checks,
        previous_run_started_at=case.previous_run_started_at,
        branched_from=BRANCHED_FROM,
    )

    assert plan == case.expected


def test_recheck_plan_edits_since_is_the_earliest_group_time() -> None:
    """Edits are read from the earliest time either group needs."""
    plan = ArtifactRecheckPlan(
        recent_ids=frozenset({"art-1"}),
        recent_since=PREVIOUS_RUN,
        recent_latest=Timestamp("2026-10-01T12:00:05Z"),
        older_ids=frozenset({"art-2"}),
        older_since=BRANCHED_FROM,
        older_latest=BRANCHED_FROM,
        always_ids=frozenset(),
    )

    assert plan.edits_since == BRANCHED_FROM

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.schema import NodeSchemaAPI, RelationshipSchemaAPI
from infrahub_sdk.schema.main import RelationshipCardinality, RelationshipKind

from infrahub.core.regeneration.members import map_subscriber_ids_by_member

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

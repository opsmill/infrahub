from __future__ import annotations

from uuid import uuid4

import pytest
from prefect.events.schemas.events import RelatedResource, Resource

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.events.constants import EventSortOrder
from infrahub.events.group_action import (
    GroupAutoCreateCappedEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedEvent,
    GroupMemberAddedEvent,
)
from infrahub.events.limits import get_prefect_max_related_resources
from infrahub.events.models import EventMeta, EventNode
from infrahub.external_protocols import ExternalAuthProtocol
from infrahub.task_manager.event import PrefectEventData
from infrahub.task_manager.models import InfrahubEventFilter


def _make_meta(account_id: str = "acct-123") -> EventMeta:
    branch = Branch(name="main")
    return EventMeta(
        branch=branch,
        context=InfrahubContext.init(
            branch=branch,
            account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=account_id),
        ).to_event_context(),
        account_id=account_id,
    )


def _make_member_added_event(
    node_id: str,
    members: list[EventNode],
    ancestors: list[EventNode] | None = None,
    kind: str = InfrahubKind.STANDARDGROUP,
) -> GroupMemberAddedEvent:
    return GroupMemberAddedEvent(
        meta=_make_meta(),
        kind=kind,
        node_id=node_id,
        members=members,
        ancestors=ancestors or [],
    )


def _old_format_related(event: GroupMemberAddedEvent) -> list[dict[str, str]]:
    """Rebuild the pre-consolidation related list for the same event.

    Members carried a duplicate ``infrahub.related.node`` entry, ancestors carried
    that duplicate plus an ``infrahub.group.update`` entry, and the group itself
    carried an ``infrahub.group.update`` entry. This is the wire format of events
    still sitting in Prefect retention when the consolidation ships.
    """
    related = event.meta.get_related()
    related.append(
        {
            "prefect.resource.id": event.node_id,
            "prefect.resource.role": "infrahub.related.node",
            "infrahub.node.kind": event.kind,
        }
    )
    related.append(
        {
            "prefect.resource.id": event.node_id,
            "prefect.resource.role": "infrahub.group.update",
            "infrahub.node.kind": event.kind,
        }
    )
    for member in event.members:
        related.append(
            {
                "prefect.resource.id": member.id,
                "prefect.resource.role": "infrahub.group.member",
                "infrahub.node.kind": member.kind,
            }
        )
        related.append(
            {
                "prefect.resource.id": member.id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": member.kind,
            }
        )
    for ancestor in event.ancestors:
        related.append(
            {
                "prefect.resource.id": ancestor.id,
                "prefect.resource.role": "infrahub.group.ancestor",
                "infrahub.node.kind": ancestor.kind,
            }
        )
        related.append(
            {
                "prefect.resource.id": ancestor.id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": ancestor.kind,
            }
        )
        related.append(
            {
                "prefect.resource.id": ancestor.id,
                "prefect.resource.role": "infrahub.group.update",
                "infrahub.node.kind": ancestor.kind,
            }
        )
    return related


def _event_data(event: GroupMemberAddedEvent, related: list[dict[str, str]]) -> PrefectEventData:
    return PrefectEventData(
        event=event.event_name,
        resource=Resource(event.get_resource()),
        related=[RelatedResource(item) for item in related],
    )


def test_group_auto_created_get_resource_pins_wire_format() -> None:
    triggering_user_id = uuid4()
    group_id = uuid4()
    event = GroupAutoCreatedEvent(
        meta=_make_meta(),
        idp="provider1",
        triggering_user_id=triggering_user_id,
        triggering_user_name="alice",
        protocol=ExternalAuthProtocol.OIDC,
        group_id=group_id,
        group_name="ops-admins",
        source_pattern=r"^(?P<name>ops-.*)$",
        origin_value="provider1",
    )

    assert event.get_resource() == {
        "prefect.resource.id": f"infrahub.account.{triggering_user_id}",
        "infrahub.account.account_id": str(triggering_user_id),
        "infrahub.account.account_name": "alice",
        "infrahub.security.idp": "provider1",
        "infrahub.security.protocol": "oidc",
        "infrahub.branch.name": "main",
        "infrahub.node.id": str(group_id),
        "infrahub.node.kind": InfrahubKind.ACCOUNTGROUP,
        "infrahub.group.name": "ops-admins",
        "infrahub.security.source_pattern": r"^(?P<name>ops-.*)$",
        "infrahub.security.origin_value": "provider1",
    }


def test_group_auto_create_rejected_get_resource_pins_wire_format() -> None:
    triggering_user_id = uuid4()
    event = GroupAutoCreateRejectedEvent(
        meta=_make_meta(),
        idp="provider1",
        triggering_user_id=triggering_user_id,
        triggering_user_name="alice",
        protocol=ExternalAuthProtocol.OAUTH2,
        rejected_claim_value="!!invalid!!",
    )

    assert event.get_resource() == {
        "prefect.resource.id": f"infrahub.account.{triggering_user_id}",
        "infrahub.account.account_id": str(triggering_user_id),
        "infrahub.account.account_name": "alice",
        "infrahub.security.idp": "provider1",
        "infrahub.security.protocol": "oauth2",
        "infrahub.branch.name": "main",
        "infrahub.security.rejected_claim_value": "!!invalid!!",
    }


def test_group_auto_create_capped_get_resource_pins_wire_format() -> None:
    triggering_user_id = uuid4()
    event = GroupAutoCreateCappedEvent(
        meta=_make_meta(),
        idp="provider1",
        triggering_user_id=triggering_user_id,
        triggering_user_name="alice",
        protocol=ExternalAuthProtocol.OIDC,
        cap_value=5,
        dropped_claims=["claim-a", "claim-b"],
        dropped_count=2,
    )

    assert event.get_resource() == {
        "prefect.resource.id": f"infrahub.account.{triggering_user_id}",
        "infrahub.account.account_id": str(triggering_user_id),
        "infrahub.account.account_name": "alice",
        "infrahub.security.idp": "provider1",
        "infrahub.security.protocol": "oidc",
        "infrahub.branch.name": "main",
        "infrahub.security.cap_value": "5",
        "infrahub.security.dropped_count": "2",
    }


def test_group_auto_created_get_related_includes_group_as_related_node() -> None:
    group_id = uuid4()
    event = GroupAutoCreatedEvent(
        meta=_make_meta(),
        idp="provider1",
        triggering_user_id=uuid4(),
        triggering_user_name="alice",
        protocol=ExternalAuthProtocol.OIDC,
        group_id=group_id,
        group_name="ops-admins",
        source_pattern=r"^(?P<name>ops-.*)$",
        origin_value="provider1",
    )

    related_nodes = [
        item for item in event.get_related() if item.get("prefect.resource.role") == "infrahub.related.node"
    ]

    assert related_nodes == [
        {
            "prefect.resource.id": str(group_id),
            "prefect.resource.role": "infrahub.related.node",
            "infrahub.node.kind": InfrahubKind.ACCOUNTGROUP,
        }
    ]


@pytest.mark.parametrize("dropped_claims", [[], ["only-one"], ["alpha", "beta", "gamma"]])
def test_group_auto_create_capped_get_related_pins_dropped_claim_shape(
    dropped_claims: list[str],
) -> None:
    event = GroupAutoCreateCappedEvent(
        meta=_make_meta(),
        idp="provider1",
        triggering_user_id=uuid4(),
        triggering_user_name="alice",
        protocol=ExternalAuthProtocol.OIDC,
        cap_value=2,
        dropped_claims=dropped_claims,
        dropped_count=len(dropped_claims),
    )

    dropped_claim_resources = [
        item for item in event.get_related() if item.get("prefect.resource.role") == "infrahub.security.dropped_claim"
    ]

    assert dropped_claim_resources == [
        {
            "prefect.resource.id": f"infrahub.security.dropped_claim.{idx}",
            "prefect.resource.role": "infrahub.security.dropped_claim",
            "infrahub.security.dropped_claim.value": claim,
        }
        for idx, claim in enumerate(dropped_claims)
    ]


def test_group_member_added_get_related_consolidates_member_and_ancestor_entries() -> None:
    """Each member and ancestor is a single entry; the duplicate roles are gone."""
    group_id = str(uuid4())
    members = [EventNode(id=str(uuid4()), kind="TestPerson") for _ in range(3)]
    ancestors = [EventNode(id=str(uuid4()), kind=InfrahubKind.STANDARDGROUP) for _ in range(2)]
    event = _make_member_added_event(node_id=group_id, members=members, ancestors=ancestors)

    related = event.get_related()

    member_entries = [item for item in related if item["prefect.resource.role"] == "infrahub.group.member"]
    assert member_entries == [
        {
            "prefect.resource.id": member.id,
            "prefect.resource.role": "infrahub.group.member",
            "infrahub.node.kind": member.kind,
        }
        for member in members
    ]

    ancestor_entries = [item for item in related if item["prefect.resource.role"] == "infrahub.group.ancestor"]
    assert ancestor_entries == [
        {
            "prefect.resource.id": ancestor.id,
            "prefect.resource.role": "infrahub.group.ancestor",
            "infrahub.node.kind": ancestor.kind,
        }
        for ancestor in ancestors
    ]

    # The only related-node entry is the group itself; members/ancestors no longer
    # carry a duplicate, and the dead group.update role is gone entirely.
    related_node_ids = [
        item["prefect.resource.id"] for item in related if item["prefect.resource.role"] == "infrahub.related.node"
    ]
    assert related_node_ids == [group_id]
    assert not [item for item in related if item["prefect.resource.role"] == "infrahub.group.update"]


def test_group_member_added_related_resources_stay_within_prefect_maximum() -> None:
    """A member add of any size keeps its event: the related list is capped."""
    max_related = get_prefect_max_related_resources()
    members = [EventNode(id=str(uuid4()), kind="TestPerson") for _ in range(max_related + 50)]
    event = _make_member_added_event(node_id=str(uuid4()), members=members)

    related = event.get_related()

    assert len(related) == max_related


def test_group_member_added_cap_keeps_fixed_and_group_scoped_entries() -> None:
    """Truncation drops overflow members, never the fixed or group-scoped entries."""
    group_id = str(uuid4())
    max_related = get_prefect_max_related_resources()
    members = [EventNode(id=str(uuid4()), kind="TestPerson") for _ in range(max_related + 50)]
    event = _make_member_added_event(node_id=group_id, members=members)

    related = event.get_related()

    related_node_ids = [
        item["prefect.resource.id"] for item in related if item["prefect.resource.role"] == "infrahub.related.node"
    ]
    assert related_node_ids == [group_id]
    assert len(related) == max_related


def test_related_node_filter_matches_old_and_new_group_event_formats() -> None:
    """One broadened filter matches a member whether it carries the old or new role."""
    member_id = str(uuid4())
    filters = InfrahubEventFilter.from_filters(order=EventSortOrder.DESC, related_node__ids=[member_id])
    assert isinstance(filters.related, list)
    spec = filters.related[-1].labels
    assert spec is not None

    old_format = [
        RelatedResource(
            root={
                "prefect.resource.id": member_id,
                "prefect.resource.role": "infrahub.related.node",
                "infrahub.node.kind": "TestPerson",
            }
        )
    ]
    new_format = [
        RelatedResource(
            root={
                "prefect.resource.id": member_id,
                "prefect.resource.role": "infrahub.group.member",
                "infrahub.node.kind": "TestPerson",
            }
        )
    ]
    ancestor_format = [
        RelatedResource(
            root={
                "prefect.resource.id": member_id,
                "prefect.resource.role": "infrahub.group.ancestor",
                "infrahub.node.kind": InfrahubKind.STANDARDGROUP,
            }
        )
    ]
    other_id = [
        RelatedResource(
            root={
                "prefect.resource.id": str(uuid4()),
                "prefect.resource.role": "infrahub.group.member",
                "infrahub.node.kind": "TestPerson",
            }
        )
    ]

    assert spec.includes(old_format) is True
    assert spec.includes(new_format) is True
    assert spec.includes(ancestor_format) is True
    assert spec.includes(other_id) is False


def test_group_event_output_identical_across_old_and_new_formats() -> None:
    """The event-query output is byte-identical whether the event is old or new format."""
    group_id = str(uuid4())
    members = [EventNode(id=str(uuid4()), kind="TestPerson") for _ in range(3)]
    ancestors = [EventNode(id=str(uuid4()), kind=InfrahubKind.STANDARDGROUP) for _ in range(2)]
    event = _make_member_added_event(node_id=group_id, members=members, ancestors=ancestors)

    new_event = _event_data(event, event.get_related())
    old_event = _event_data(event, _old_format_related(event))

    expected_related_nodes = [{"id": node.id, "kind": node.kind} for node in members + ancestors]
    assert new_event.get_related_nodes() == expected_related_nodes
    assert old_event.get_related_nodes() == expected_related_nodes

    expected_group = {
        "members": [{"id": member.id, "kind": member.kind} for member in members],
        "ancestors": [{"id": ancestor.id, "kind": ancestor.kind} for ancestor in ancestors],
    }
    assert new_event._return_group_event() == expected_group
    assert old_event._return_group_event() == expected_group

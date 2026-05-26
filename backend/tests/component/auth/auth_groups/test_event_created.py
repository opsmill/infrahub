from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth import signin_sso_account
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccountGroup
from infrahub.events.group_action import GroupAutoCreatedEvent
from infrahub.external_protocols import ExternalAuthProtocol
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.identities import make_identity

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_event_emitted_once_on_successful_auto_creation(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
) -> None:
    """A first-time login with a matching claim emits exactly one `GroupAutoCreatedEvent`.

    The payload carries the local group name, the configured provider name, the source pattern,
    and the triggering user identity.
    """
    recorder = MemoryInfrahubEvent()
    identity = make_identity(sub="sub-event-created-001", provider_name="AzureAD-corp")

    await signin_sso_account(
        db=db,
        external_identity=identity,
        sso_groups=["LDAP/group/team-event-created"],
        event_service=recorder,
    )

    created_events = [event for event in recorder.events if isinstance(event, GroupAutoCreatedEvent)]
    assert len(created_events) == 1, "exactly one GroupAutoCreatedEvent must be emitted"

    event = created_events[0]
    groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "team-event-created"})
    assert len(groups) == 1
    expected_account = await NodeManager.query(db=db, schema="CoreAccount", filters={"name__value": "Alice Auto"})
    assert len(expected_account) == 1

    assert event.group_name == "team-event-created"
    assert str(event.group_id) == groups[0].id
    assert event.source_pattern == r"^LDAP/group/(?P<name>.+)$"
    assert event.origin_value == "AzureAD-corp"
    assert event.idp == "AzureAD-corp"
    assert event.idp == event.origin_value
    assert event.protocol == ExternalAuthProtocol.OIDC
    assert event.triggering_user_name == "Alice Auto"
    assert str(event.triggering_user_id) == expected_account[0].id


async def test_no_event_emitted_when_existing_group_is_reused(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
) -> None:
    """A second login for the same external claim reuses the existing group.

    No second `GroupAutoCreatedEvent` must be emitted for the reuse path.
    """
    first_recorder = MemoryInfrahubEvent()
    second_recorder = MemoryInfrahubEvent()

    identity_first = make_identity(sub="sub-event-reuse-1", display_name="Carla Auto")
    identity_second = make_identity(sub="sub-event-reuse-2", display_name="Dimi Auto")

    await signin_sso_account(
        db=db,
        external_identity=identity_first,
        sso_groups=["LDAP/group/team-event-reuse"],
        event_service=first_recorder,
    )
    await signin_sso_account(
        db=db,
        external_identity=identity_second,
        sso_groups=["LDAP/group/team-event-reuse"],
        event_service=second_recorder,
    )

    first_created = [event for event in first_recorder.events if isinstance(event, GroupAutoCreatedEvent)]
    second_created = [event for event in second_recorder.events if isinstance(event, GroupAutoCreatedEvent)]

    assert len(first_created) == 1, "first login must emit one GroupAutoCreatedEvent"
    assert second_created == [], "reuse of an existing auto-created group must NOT emit a GroupAutoCreatedEvent"

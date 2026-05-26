from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth import signin_sso_account
from infrahub.events.group_action import GroupAutoCreateCappedEvent, GroupAutoCreatedEvent
from infrahub.external_protocols import ExternalAuthProtocol
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.identities import make_identity

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_cap_breach_event_emitted_with_dropped_claims_verbatim(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_with_low_cap: int,
) -> None:
    """A login that breaches the per-login cap emits exactly one `GroupAutoCreateCappedEvent`.

    The payload carries the cap value, the count of dropped claims, and the verbatim per-entry
    dropped claims.
    """
    recorder = MemoryInfrahubEvent()
    cap = autocreate_filter_with_low_cap  # 2
    identity = make_identity(sub="sub-cap-breach", display_name="Nora Cap")
    claims = [
        "LDAP/group/cap-team-one",
        "LDAP/group/cap-team-two",
        "LDAP/group/cap-team-three",
        "LDAP/group/cap-team-four",
    ]

    await signin_sso_account(
        db=db,
        external_identity=identity,
        sso_groups=claims,
        event_service=recorder,
    )

    cap_events = [event for event in recorder.events if isinstance(event, GroupAutoCreateCappedEvent)]
    created_events = [event for event in recorder.events if isinstance(event, GroupAutoCreatedEvent)]

    assert len(cap_events) == 1, "exactly one GroupAutoCreateCappedEvent must be emitted per breaching login"
    assert len(created_events) == cap, "only `cap` new groups must be created before the breach"

    event = cap_events[0]
    assert event.cap_value == cap
    assert event.dropped_count == len(claims) - cap
    assert event.dropped_claims == claims[cap:]
    assert event.idp == "AzureAD-corp"
    assert event.protocol == ExternalAuthProtocol.OIDC


async def test_no_cap_breach_event_when_below_cap(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_with_low_cap: int,
) -> None:
    """A login that creates fewer new groups than the cap must NOT emit a cap-breach event."""
    recorder = MemoryInfrahubEvent()
    identity = make_identity(sub="sub-cap-below", display_name="Owen Cap")
    claims = ["LDAP/group/below-cap-team-one"]

    await signin_sso_account(
        db=db,
        external_identity=identity,
        sso_groups=claims,
        event_service=recorder,
    )

    cap_events = [event for event in recorder.events if isinstance(event, GroupAutoCreateCappedEvent)]
    created_events = [event for event in recorder.events if isinstance(event, GroupAutoCreatedEvent)]

    assert cap_events == []
    assert len(created_events) == 1

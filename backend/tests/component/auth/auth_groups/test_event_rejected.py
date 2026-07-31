from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

import pytest

from infrahub import config
from infrahub.auth.auth import signin_sso_account
from infrahub.auth.auth_groups.emitter import MAX_CLAIM_VALUE_LENGTH
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccountGroup
from infrahub.events.group_action import GroupAutoCreatedEvent, GroupAutoCreateRejectedEvent
from infrahub.external_protocols import ExternalAuthProtocol
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.identities import make_identity

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
def autocreate_filter_allows_empty_name() -> Iterator[None]:
    """Activate a filter whose named capture can produce an empty or whitespace effective name."""
    original_filter = config.SETTINGS.security.auto_create_groups_filter
    original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns

    config.SETTINGS.security.auto_create_groups_filter = r"^LDAP/group/(?P<name>.*)$"
    config.SETTINGS.security.recompile_auto_create_groups_filter_patterns()

    try:
        yield
    finally:
        config.SETTINGS.security.auto_create_groups_filter = original_filter
        config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled


async def test_rejected_claim_event_emitted_for_empty_effective_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_allows_empty_name: None,
) -> None:
    """A claim whose captured `name` is the empty string fails identifier validation.

    The login completes, no group is created, and a `GroupAutoCreateRejectedEvent` is
    emitted with the original claim stored verbatim.
    """
    recorder = MemoryInfrahubEvent()
    identity = make_identity(sub="sub-reject-empty", display_name="Eli Auto")

    await signin_sso_account(
        db=db,
        external_identity=identity,
        sso_groups=["LDAP/group/"],
        event_service=recorder,
    )

    rejected_events = [event for event in recorder.events if isinstance(event, GroupAutoCreateRejectedEvent)]
    created_events = [event for event in recorder.events if isinstance(event, GroupAutoCreatedEvent)]

    assert len(rejected_events) == 1, "exactly one GroupAutoCreateRejectedEvent must be emitted"
    assert created_events == [], "no group must be created for an invalid effective name"

    event = rejected_events[0]
    assert event.rejected_claim_value == "LDAP/group/"
    assert event.idp == "AzureAD-corp"
    assert event.protocol == ExternalAuthProtocol.OIDC
    assert event.triggering_user_name == "Eli Auto"

    groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": ""})
    assert len(groups) == 0


async def test_rejected_claim_event_truncates_long_claim_verbatim(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_allows_empty_name: None,
) -> None:
    """A rejected claim that exceeds the documented upper bound is stored verbatim up to truncation.

    The payload remains identical to the original claim prefix.
    """
    recorder = MemoryInfrahubEvent()
    long_whitespace = " " * 2048
    claim = "LDAP/group/" + long_whitespace
    identity = make_identity(sub="sub-reject-long", display_name="Lena Auto")

    await signin_sso_account(
        db=db,
        external_identity=identity,
        sso_groups=[claim],
        event_service=recorder,
    )

    rejected_events = [event for event in recorder.events if isinstance(event, GroupAutoCreateRejectedEvent)]
    assert len(rejected_events) == 1
    truncated = rejected_events[0].rejected_claim_value
    assert claim.startswith(truncated), "truncated value must be a verbatim prefix of the original claim"
    assert len(truncated) == MAX_CLAIM_VALUE_LENGTH, (
        "truncated value must be exactly MAX_CLAIM_VALUE_LENGTH when the original exceeds it"
    )

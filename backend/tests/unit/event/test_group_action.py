from __future__ import annotations

from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.events.group_action import (
    GroupAutoCreateCapBreachEvent,
    GroupAutoCreatedEvent,
    GroupAutoCreateRejectedClaimEvent,
)
from infrahub.events.models import EventMeta
from infrahub.external_protocols import ExternalAuthProtocol


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


def test_group_auto_create_rejected_claim_get_resource_pins_wire_format() -> None:
    triggering_user_id = uuid4()
    event = GroupAutoCreateRejectedClaimEvent(
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


def test_group_auto_create_cap_breach_get_resource_pins_wire_format() -> None:
    triggering_user_id = uuid4()
    event = GroupAutoCreateCapBreachEvent(
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


@pytest.mark.parametrize("dropped_claims", [[], ["only-one"], ["alpha", "beta", "gamma"]])
def test_group_auto_create_cap_breach_get_related_pins_dropped_claim_shape(
    dropped_claims: list[str],
) -> None:
    event = GroupAutoCreateCapBreachEvent(
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

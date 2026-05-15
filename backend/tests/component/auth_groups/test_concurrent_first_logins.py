"""Concurrency safety test for the auto-creation flow.

N simultaneous first-logins for the same brand-new external claim must produce exactly one local
`CoreAccountGroup` row, and every involved login must succeed. Serialization is provided by
`lock.registry.get(name=..., namespace="auto-create-group")` inside the service module. Hits the
real test database — no mocking.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.auth import ExternalAuthProtocol, ExternalIdentity, signin_sso_account
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccount, CoreAccountGroup

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
def autocreate_filter_enabled() -> Iterator[None]:
    """Enable the auto-creation filter for the duration of the test, restoring on teardown."""
    original_filter = config.SETTINGS.security.auto_create_groups_filter
    original_compiled = config.SETTINGS.security._auto_create_groups_filter_patterns

    config.SETTINGS.security.auto_create_groups_filter = r"^LDAP/group/(?P<name>.+)$"
    config.SETTINGS.security._compile_auto_create_groups_filter_patterns()

    try:
        yield
    finally:
        config.SETTINGS.security.auto_create_groups_filter = original_filter
        config.SETTINGS.security._auto_create_groups_filter_patterns = original_compiled


def _make_identity(index: int, *, provider_name: str = "AzureAD-corp") -> ExternalIdentity:
    return ExternalIdentity(
        sub=f"sub-concurrent-{index:03d}",
        provider_name=provider_name,
        protocol=ExternalAuthProtocol.OIDC,
        display_name=f"Concurrent User {index}",
        email=f"concurrent.user.{index}@example.com",
    )


async def test_concurrent_first_logins_produce_exactly_one_group(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
) -> None:
    """N simultaneous first-logins for the same brand-new external claim must result in exactly
    one `CoreAccountGroup` row, every login succeeding.

    All N users carry the same external claim `LDAP/group/concurrent-target`. Under the lock,
    the first-arriving login creates the group; subsequent logins find it under the re-check and
    skip the create, but still add their account as a member.
    """
    concurrency = 8
    identities = [_make_identity(i) for i in range(concurrency)]

    # Fire all sign-ins concurrently — the auto-creation service is responsible for serializing
    # the find-or-create step via the distributed lock.
    results = await asyncio.gather(
        *(
            signin_sso_account(db=db, external_identity=identity, sso_groups=["LDAP/group/concurrent-target"])
            for identity in identities
        ),
        return_exceptions=True,
    )

    # Every login must succeed — no exception leaks through.
    for index, result in enumerate(results):
        assert not isinstance(result, BaseException), f"sign-in {index} raised {type(result).__name__}: {result}"

    # Exactly one group row exists (no duplicates from the race).
    groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "concurrent-target"})
    assert len(groups) == 1, "concurrent first-logins must produce exactly one group"
    assert groups[0].origin.value == "AzureAD-corp"

    # Every account is a member of that group.
    refreshed = await NodeManager.get_one(db=db, id=groups[0].id, prefetch_relationships=True)
    members = await refreshed.members.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)

    accounts = await NodeManager.query(
        db=db, schema=InfrahubKind.ACCOUNT, filters={"name__values": [i.display_name for i in identities]}
    )
    assert {a.id for a in accounts} <= set(members), "every concurrent user must be a member"

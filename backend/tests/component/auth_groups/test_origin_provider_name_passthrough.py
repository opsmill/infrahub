"""Component test: configured provider name passes through verbatim to `origin`.

Two distinct providers must produce two groups whose `origin` values match the input strings exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.auth import ExternalAuthProtocol, ExternalIdentity, signin_sso_account
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreAccountGroup

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize(
    ("provider_name", "captured_name"),
    [
        pytest.param("AzureAD-corp", "team-alpha", id="azure"),
        pytest.param("corp-ldap", "team-beta", id="ldap"),
    ],
)
async def test_provider_name_is_written_verbatim_to_origin(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
    provider_name: str,
    captured_name: str,
) -> None:
    """A single provider authenticating one login produces one group with `origin == provider_name`."""
    identity = ExternalIdentity(
        sub=f"sub-passthrough-{provider_name.lower()}",
        provider_name=provider_name,
        protocol=ExternalAuthProtocol.OIDC,
        display_name=f"Passthrough {provider_name}",
        email=f"passthrough.{provider_name.lower()}@example.com",
    )

    await signin_sso_account(db=db, external_identity=identity, sso_groups=[f"LDAP/group/{captured_name}"])

    groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": captured_name})
    assert len(groups) == 1
    assert groups[0].origin.value == provider_name


async def test_two_providers_produce_two_groups_with_distinct_origin_values(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    autocreate_filter_enabled: None,
) -> None:
    """Two distinct providers triggering two separate logins produce two groups whose `origin`
    values match the configured names verbatim.
    """
    azure_identity = ExternalIdentity(
        sub="sub-passthrough-azure",
        provider_name="AzureAD-corp",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Pia Azure",
        email="pia.azure@example.com",
    )
    ldap_identity = ExternalIdentity(
        sub="sub-passthrough-ldap",
        provider_name="corp-ldap",
        protocol=ExternalAuthProtocol.OIDC,
        display_name="Lou LDAP",
        email="lou.ldap@example.com",
    )

    await signin_sso_account(db=db, external_identity=azure_identity, sso_groups=["LDAP/group/azure-only-team"])
    await signin_sso_account(db=db, external_identity=ldap_identity, sso_groups=["LDAP/group/ldap-only-team"])

    azure_groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "azure-only-team"})
    ldap_groups = await NodeManager.query(db=db, schema=CoreAccountGroup, filters={"name__value": "ldap-only-team"})

    assert len(azure_groups) == 1
    assert len(ldap_groups) == 1
    assert azure_groups[0].origin.value == "AzureAD-corp"
    assert ldap_groups[0].origin.value == "corp-ldap"

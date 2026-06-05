from __future__ import annotations

from infrahub.auth.auth import ExternalIdentity
from infrahub.external_protocols import ExternalAuthProtocol


def make_identity(
    *,
    sub: str,
    provider_name: str = "AzureAD-corp",
    display_name: str = "Alice Auto",
    protocol: ExternalAuthProtocol = ExternalAuthProtocol.OIDC,
) -> ExternalIdentity:
    return ExternalIdentity(
        sub=sub,
        provider_name=provider_name,
        protocol=protocol,
        display_name=display_name,
        email=f"{display_name.lower().replace(' ', '.')}@example.com",
    )

"""Shared vocabulary for external-system protocols Infrahub interoperates with.

Top-level leaf module — depends on nothing in `infrahub.*`. Owned by no single domain:
the auth flows dispatch on these values, and audit events carry them as provenance
fields. Living here (rather than under `auth/`) keeps both consumers reachable without
either having to load the other's package init.
"""

from __future__ import annotations

from enum import StrEnum


class ExternalAuthProtocol(StrEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    LDAP = "ldap"

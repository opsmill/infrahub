"""Value types shared across the auth domain.

Leaf module — no imports from `infrahub.auth.auth` or `infrahub.events.*`. Other layers
(notably `infrahub.events.models` and `infrahub.events.group_action`) depend on these types
and must be able to reach them without triggering the auth-package load cycle.
"""

from __future__ import annotations

from enum import StrEnum


class AuthType(StrEnum):
    NONE = "none"
    JWT = "jwt"
    API = "api"


class ExternalAuthProtocol(StrEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    LDAP = "ldap"

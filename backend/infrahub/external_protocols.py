"""Shared vocabulary for external-system protocols Infrahub interoperates with."""

from __future__ import annotations

from enum import StrEnum


class ExternalAuthProtocol(StrEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    LDAP = "ldap"

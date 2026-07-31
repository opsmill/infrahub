"""Value types shared across the auth domain."""

from __future__ import annotations

from enum import StrEnum


class AuthType(StrEnum):
    NONE = "none"
    JWT = "jwt"
    API = "api"

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from infrahub.exceptions import EnterpriseRequiredError

if TYPE_CHECKING:
    from infrahub.auth import AuthResult
    from infrahub.database import InfrahubDatabase


LDAP_AUTH_FEATURE_NAME = "ldap_auth"


class LDAPAuthService(ABC):
    """Abstract base for LDAP authentication."""

    @abstractmethod
    async def authenticate(self, db: InfrahubDatabase, username: str, password: str) -> AuthResult:
        """Authenticate `username`/`password` against the configured directory.

        Returns an `AuthResult` on success - same shape as the local-login and
        OAuth2/OIDC flows so downstream consumers cannot distinguish the
        authentication method from the session alone.

        Raises:
            EnterpriseRequiredError: when invoked on a community deployment.
            LDAPAuthenticationError: on any credential/lookup/disabled-account failure.
            LDAPDirectoryUnavailableError: when every configured server is unreachable.
            LDAPCollisionError: when the username collides with an existing local-only Infrahub account.

        """


class LDAPAuthServiceCommunity(LDAPAuthService):
    async def authenticate(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        username: str,  # noqa: ARG002
        password: str,  # noqa: ARG002
    ) -> AuthResult:
        raise EnterpriseRequiredError(feature=LDAP_AUTH_FEATURE_NAME)

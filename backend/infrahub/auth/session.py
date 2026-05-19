"""In-memory representation of an authenticated session.

Leaf module — only depends on `infrahub.auth.types`. Other layers (notably
`infrahub.events.models`) import `AccountSession` from here and must be able to do so without
triggering the auth-package load cycle.
"""

from __future__ import annotations

from pydantic import BaseModel, PrivateAttr

from infrahub.auth.types import AuthType


class AccountSession(BaseModel):
    authenticated: bool = True
    account_id: str
    session_id: str | None = None
    auth_type: AuthType

    _original_account_id: str | None = PrivateAttr(default=None)

    @property
    def authenticated_by_jwt(self) -> bool:
        return self.auth_type == AuthType.JWT

    @property
    def authenticating_account_id(self) -> str:
        """ID of the account that originally authenticated this session.

        Falls back to `account_id` until `override_account` is called; once a context
        swap occurs `account_id` reflects the impersonated account, so this is the only
        stable reference back to the real caller.
        """
        return self._original_account_id if self._original_account_id is not None else self.account_id

    def override_account(self, account_id: str) -> None:
        """Switch the active account, preserving the original on first call."""
        if self._original_account_id is None:
            self._original_account_id = self.account_id
        self.account_id = account_id

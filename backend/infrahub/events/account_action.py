from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import Field

from infrahub.utils import InfrahubStringEnum

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class AuthMethod(InfrahubStringEnum):
    PASSWORD = "password"
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class SSOProvider(InfrahubStringEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class AccountType(InfrahubStringEnum):
    USER = "USER"
    SCRIPT = "SCRIPT"


class AccountLoggedInEvent(InfrahubEvent):
    """Emitted when a user successfully authenticates."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.account.logged_in"

    account_id: str = Field(..., description="UUID of the account")
    account_name: str = Field(..., description="Username of the account")
    account_type: AccountType = Field(..., description="USER or SCRIPT")
    auth_method: AuthMethod = Field(..., description="How they authenticated")
    session_id: str = Field(..., description="UUID of the session")
    groups: list[str] = Field(default_factory=list, description="List of group names/IDs")
    roles: list[str] = Field(default_factory=list, description="List of role names/IDs")
    sso_provider: SSOProvider | None = Field(default=None, description="SSO provider name (if applicable)")
    client_ip: str | None = Field(default=None, description="Source IP address")
    user_agent: str | None = Field(default=None, description="Browser/client info")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="When the login occurred (UTC)",
    )

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.account.{self.account_id}",
            "infrahub.account.name": self.account_name,
            "infrahub.account.auth_method": self.auth_method,
            "infrahub.account.session_id": self.session_id,
        }


class AccountLoggedOutEvent(InfrahubEvent):
    """Emitted when a user explicitly logs out."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.account.logged_out"

    account_id: str = Field(..., description="UUID of the account")
    account_name: str = Field(..., description="Username of the account")
    session_id: str = Field(..., description="UUID of the session being terminated")
    logout_type: str = Field(default="user_initiated", description="How logout occurred")
    client_ip: str | None = Field(default=None, description="Source IP address")
    user_agent: str | None = Field(default=None, description="Browser/client info")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="When the logout occurred (UTC)",
    )

    def get_resource(self) -> dict[str, str]:
        return {
            "prefect.resource.id": f"infrahub.account.{self.account_id}",
            "infrahub.account.name": self.account_name,
            "infrahub.account.session_id": self.session_id,
            "infrahub.account.logout_type": self.logout_type,
        }

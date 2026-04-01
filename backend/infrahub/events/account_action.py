from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import Field

from infrahub.core.constants import AccountType, InfrahubKind
from infrahub.utils import InfrahubStringEnum

from .constants import EVENT_NAMESPACE
from .models import InfrahubEvent


class AuthMethod(InfrahubStringEnum):
    PASSWORD = "password"
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class AccountLoggedInEvent(InfrahubEvent):
    """Emitted when a user successfully authenticates."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.account.logged_in"

    kind: str = Field(..., description="The type of account object")
    account_id: str = Field(..., description="UUID of the account")
    account_name: str = Field(..., description="Username of the account")
    account_type: AccountType = Field(..., description="USER or SCRIPT")
    auth_method: AuthMethod = Field(..., description="How they authenticated")
    session_id: str = Field(..., description="UUID of the session")
    groups: list[dict[str, str]] = Field(default_factory=list, description="List of group names/IDs")
    roles: list[dict[str, str]] = Field(default_factory=list, description="List of role names/IDs")
    sso_provider: str | None = Field(default=None, description="SSO provider name (if applicable)")
    client_ip: str | None = Field(default=None, description="Source IP address")
    user_agent: str | None = Field(default=None, description="Browser/client info")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=UTC),
        description="When the login occurred (UTC)",
    )

    def get_resource(self) -> dict[str, str]:
        resource = {
            "prefect.resource.id": f"infrahub.account.{self.account_id}",
            "infrahub.account.kind": self.kind,
            "infrahub.node.id": self.account_id,
            "infrahub.node.kind": self.kind,
            "infrahub.account.account_id": self.account_id,
            "infrahub.account.account_name": self.account_name,
            "infrahub.account.account_type": self.account_type.value,
            "infrahub.account.auth_method": self.auth_method.value,
            "infrahub.account.session_id": self.session_id,
            "infrahub.account.timestamp": self.timestamp.isoformat(),
        }
        if self.sso_provider:
            resource["infrahub.account.sso_provider"] = self.sso_provider
        if self.client_ip:
            resource["infrahub.account.client_ip"] = self.client_ip
        if self.user_agent:
            resource["infrahub.account.user_agent"] = self.user_agent
        return resource

    def get_related(self) -> list[dict[str, str]]:
        related = super().get_related()
        for group in self.groups:
            for group_id, group_name in group.items():
                related.append(
                    {
                        "prefect.resource.id": group_id,
                        "prefect.resource.role": "infrahub.related.node",
                        "infrahub.node.kind": InfrahubKind.ACCOUNTGROUP,
                        "infrahub.node.name": group_name,
                    }
                )

        for role in self.roles:
            for role_id, role_name in role.items():
                related.append(
                    {
                        "prefect.resource.id": role_id,
                        "prefect.resource.role": "infrahub.related.node",
                        "infrahub.node.kind": InfrahubKind.ACCOUNTROLE,
                        "infrahub.node.name": role_name,
                    }
                )
        return related


class AccountLoggedOutEvent(InfrahubEvent):
    """Emitted when a user explicitly logs out."""

    event_name: ClassVar[str] = f"{EVENT_NAMESPACE}.account.logged_out"

    kind: str = Field(..., description="The type of account object")
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
        resource = {
            "prefect.resource.id": f"infrahub.account.{self.account_id}",
            "infrahub.node.id": self.account_id,
            "infrahub.node.kind": self.kind,
            "infrahub.account.kind": self.kind,
            "infrahub.account.account_id": self.account_id,
            "infrahub.account.account_name": self.account_name,
            "infrahub.account.session_id": self.session_id,
            "infrahub.account.logout_type": self.logout_type,
            "infrahub.account.timestamp": self.timestamp.isoformat(),
        }
        if self.client_ip:
            resource["infrahub.account.client_ip"] = self.client_ip
        if self.user_agent:
            resource["infrahub.account.user_agent"] = self.user_agent
        return resource

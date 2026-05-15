from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

import bcrypt
import jwt
from pydantic import BaseModel, PrivateAttr

from infrahub import config, lock, models
from infrahub.auth_groups.filter import ClaimFilter
from infrahub.auth_groups.service import AutoCreatedGroups
from infrahub.config import (
    SecurityOAuth2Google,
    SecurityOAuth2Settings,
    SecurityOIDCGoogle,
    SecurityOIDCSettings,
)
from infrahub.core.account import validate_token
from infrahub.core.constants import AccountStatus, AccountType, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup, CoreAccountRole, CoreGenericAccount
from infrahub.core.registry import registry
from infrahub.exceptions import AuthorizationError, GatewayError, NodeNotFoundError, ProcessingError
from infrahub.log import get_logger

if TYPE_CHECKING:
    import httpx

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

log = get_logger()


class AuthResult(BaseModel):
    """Rich result returned from successful authentication, combining token with account metadata."""

    model_config = {"frozen": True}

    token: models.UserToken
    kind: str
    account_id: str
    account_name: str
    account_type: AccountType
    session_id: uuid.UUID
    groups: list[dict[str, str]]
    roles: list[dict[str, str]]


class AuthType(StrEnum):
    NONE = "none"
    JWT = "jwt"
    API = "api"


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


class SSOStateCache(BaseModel):
    """Cache data stored during OAuth2/OIDC authorization flow.

    This model is used to store state information between the authorization
    request and the token exchange, including PKCE code_verifier when enabled.
    """

    final_url: str
    code_verifier: str | None = None


async def fetch_account_groups_and_roles(
    db: InfrahubDatabase, account_id: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Fetch group and role {id: name} for an account. Returns empty lists on any failure."""
    group_names: list[dict[str, str]] = []
    role_names: list[dict[str, str]] = []

    groups = await NodeManager.query(
        schema=CoreAccountGroup,
        db=db,
        filters={"members__ids": [account_id]},
    )
    group_names.extend({g.get_id(): g.name.value} for g in groups)
    for group in groups:
        roles = await group.roles.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccountRole)
        role_names.extend({r.get_id(): r.name.value} for r in roles.values())

    return group_names, role_names


class ExternalAuthProtocol(StrEnum):
    OAUTH2 = "oauth2"
    OIDC = "oidc"


class ExternalIdentity(BaseModel):
    sub: str  # provider-issued subject identifier
    provider_name: str  # as configured in Infrahub, e.g. "google", "provider1"
    protocol: ExternalAuthProtocol
    display_name: str  # user_info["name"] — used as label and as name on creation (if no conflict)
    email: str  # user_info["email"] — fallback for name when display_name is already taken


async def validate_active_account(db: InfrahubDatabase, account_id: str) -> None:
    account = await NodeManager.get_one(db=db, kind=CoreGenericAccount, id=account_id, raise_on_error=True)
    if account.status.value != AccountStatus.ACTIVE.value:
        raise AuthorizationError("This account has been deactivated")


async def authenticate_with_password(
    db: InfrahubDatabase, credentials: models.PasswordCredential, branch: str | None = None
) -> AuthResult:
    selected_branch = await registry.get_branch(db=db, branch=branch)

    response = await NodeManager.query(
        schema=CoreGenericAccount,
        db=db,
        branch=selected_branch,
        filters={"name__value": credentials.username},
        limit=1,
    )

    if not response:
        raise NodeNotFoundError(
            branch_name=selected_branch.name,
            node_type=InfrahubKind.GENERICACCOUNT,
            identifier=credentials.username,
            message="That login user doesn't exist in the system",
        )

    account = response[0]
    if account.status.value != AccountStatus.ACTIVE.value:
        raise AuthorizationError("This account is not allowed to login")

    password = account.password.value
    valid_credentials = bcrypt.checkpw(credentials.password.encode("UTF-8"), str(password or "").encode("UTF-8"))
    if not valid_credentials:
        raise AuthorizationError("Incorrect password")

    now = datetime.now(tz=UTC)
    refresh_expires = now + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)

    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)

    groups, roles = await fetch_account_groups_and_roles(db=db, account_id=account.id)

    return AuthResult(
        token=models.UserToken(access_token=access_token, refresh_token=refresh_token),
        account_id=account.id,
        account_name=account.name.value,
        account_type=account.account_type.value,
        session_id=session_id,
        groups=groups,
        roles=roles,
        kind=account.get_kind(),
    )


async def create_db_refresh_token(db: InfrahubDatabase, account_id: str, expiration: datetime) -> uuid.UUID:
    obj = await Node.init(db=db, schema=InfrahubKind.REFRESHTOKEN)
    await obj.new(db=db, account=account_id, expiration=expiration.isoformat())
    await obj.save(db=db)
    return uuid.UUID(obj.id)


async def create_fresh_access_token(
    db: InfrahubDatabase, refresh_data: models.RefreshTokenData
) -> models.AccessTokenResponse:
    selected_branch = await registry.get_branch(db=db)

    refresh_token = await NodeManager.get_one(id=str(refresh_data.session_id), db=db)
    if not refresh_token:
        raise AuthorizationError("The provided refresh token has been invalidated in the database")

    account = await NodeManager.get_one(id=refresh_data.account_id, kind=CoreGenericAccount, db=db)
    if not account:
        raise NodeNotFoundError(
            branch_name=selected_branch.name,
            node_type="Account",
            identifier=refresh_data.account_id,
            message="That login user doesn't exist in the system",
        )

    access_token = generate_access_token(account_id=account.id, session_id=refresh_data.session_id)

    return models.AccessTokenResponse(access_token=access_token)


async def signin_sso_account(
    db: InfrahubDatabase, external_identity: ExternalIdentity, sso_groups: list[str]
) -> AuthResult:
    existing_identity = await _find_existing_identity(db=db, external_identity=external_identity)
    if existing_identity is not None:
        account = await _account_from_existing_identity(
            db=db, identity_node=existing_identity, external_identity=external_identity
        )
    else:
        account = await _create_account_for_new_identity(db=db, external_identity=external_identity)

    await _assign_group_memberships(db=db, account=account, external_identity=external_identity, sso_groups=sso_groups)
    return await _build_signin_result(db=db, account=account)


async def _find_existing_identity(*, db: InfrahubDatabase, external_identity: ExternalIdentity) -> Node | None:
    """Look up the `CoreExternalIdentity` row for `(sub, provider_name, protocol)`, or `None`."""
    matches = await NodeManager.query(
        db=db,
        schema=InfrahubKind.EXTERNALIDENTITY,
        filters={
            "sub__value": external_identity.sub,
            "provider_name__value": external_identity.provider_name,
            "protocol__value": external_identity.protocol,
        },
        prefetch_relationships=True,
        limit=1,
    )
    return matches[0] if matches else None


async def _account_from_existing_identity(
    *, db: InfrahubDatabase, identity_node: Node, external_identity: ExternalIdentity
) -> Node:
    """Return the account linked to an existing identity, refreshing its label when stale."""
    account = await identity_node.get_relationship(name="account").get_peer(db=db, raise_on_error=True)
    await _refresh_label_if_stale(db=db, account=account, display_name=external_identity.display_name)
    return account


async def _create_account_for_new_identity(*, db: InfrahubDatabase, external_identity: ExternalIdentity) -> Node:
    """Resolve or create the account for a never-before-seen external identity.

    Serialized through the `sso-account` lock so concurrent first-logins for the same identity
    cannot produce duplicate rows. Three outcomes:

    - An account with that `display_name` already exists and has **no** linked identity →
      link this identity to it (unclaimed-account transition).
    - An account with that `display_name` already exists and **is claimed** by another SSO
      user → create a new account using `email` as the unique `name`. If `email` is also
      already taken as a `name`, raise.
    - No account by that name → create a new account with `display_name` as its `name`.
    """
    lock_key = f"{external_identity.protocol}:{external_identity.provider_name}:{external_identity.sub}"
    async with lock.registry.get(name=lock_key, namespace="sso-account"):
        account_by_name = await NodeManager.get_one_by_default_filter(
            db=db, id=external_identity.display_name, kind=InfrahubKind.ACCOUNT
        )

        if account_by_name is not None and not await _account_has_identity(db=db, account=account_by_name):
            return await _link_unclaimed_account(db=db, account=account_by_name, external_identity=external_identity)

        account_name = await _pick_account_name(
            db=db, external_identity=external_identity, name_collision=account_by_name is not None
        )
        return await _create_account_with_identity(
            db=db, account_name=account_name, external_identity=external_identity
        )


async def _account_has_identity(*, db: InfrahubDatabase, account: Node) -> bool:
    identities = await NodeManager.query(
        db=db,
        schema=InfrahubKind.EXTERNALIDENTITY,
        filters={"account__ids": [account.id]},
        limit=1,
    )
    return bool(identities)


async def _link_unclaimed_account(*, db: InfrahubDatabase, account: Node, external_identity: ExternalIdentity) -> Node:
    """Attach the new external identity to an existing local-only account."""
    await _create_identity_node(db=db, account=account, external_identity=external_identity)
    await _refresh_label_if_stale(db=db, account=account, display_name=external_identity.display_name)
    return account


async def _pick_account_name(*, db: InfrahubDatabase, external_identity: ExternalIdentity, name_collision: bool) -> str:
    """Pick the `name` for a new account, falling back to email on display-name collision."""
    if not name_collision:
        return external_identity.display_name

    existing_by_email = await NodeManager.get_one_by_default_filter(
        db=db, id=external_identity.email, kind=InfrahubKind.ACCOUNT
    )
    if existing_by_email is not None:
        raise ProcessingError(
            message=(
                f"Cannot create account: both '{external_identity.display_name}'"
                f" and '{external_identity.email}' are already in use as account names."
            )
        )
    return external_identity.email


async def _create_account_with_identity(
    *, db: InfrahubDatabase, account_name: str, external_identity: ExternalIdentity
) -> Node:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(
        db=db,
        name=account_name,
        label=external_identity.display_name,
        account_type="User",
        password=str(uuid.uuid4()),
    )
    await account.save(db=db)
    await _create_identity_node(db=db, account=account, external_identity=external_identity)
    return account


async def _create_identity_node(*, db: InfrahubDatabase, account: Node, external_identity: ExternalIdentity) -> None:
    identity_node = await Node.init(db=db, schema=InfrahubKind.EXTERNALIDENTITY)
    await identity_node.new(
        db=db,
        sub=external_identity.sub,
        provider_name=external_identity.provider_name,
        protocol=external_identity.protocol,
        account=account.id,
    )
    await identity_node.save(db=db)


async def _refresh_label_if_stale(*, db: InfrahubDatabase, account: Node, display_name: str) -> None:
    typed = cast("CoreAccount", account)
    if typed.label.value == display_name:
        return
    typed.label.value = display_name
    await typed.save(db=db)


async def _assign_group_memberships(
    *,
    db: InfrahubDatabase,
    account: Node,
    external_identity: ExternalIdentity,
    sso_groups: list[str],
) -> None:
    """Attach the account to local groups derived from the external claims.

    Resolution order:
      1. If the auto-create filter is configured, evaluate every claim against it. Membership
         goes to the matched (created-or-reused) `CoreAccountGroup` rows. Claims that do not
         match are silently skipped.
      2. If auto-create produced no memberships (filter inactive, or active but no claim
         matched), and `sso_user_default_group` is configured, add the account to that default
         group.
      3. Otherwise, the legacy exact-name lookup runs against the raw `sso_groups`.
    """
    if config.SETTINGS.security.auto_create_groups_enabled:
        granted = await AutoCreatedGroups(
            db=db,
            account=account,
            provider_name=external_identity.provider_name,
        ).assign(
            claims=sso_groups,
            claim_filter=ClaimFilter(patterns=config.SETTINGS.security.auto_create_groups_filter_patterns),
        )
        if granted:
            return
        # Filter active but produced nothing: per FR-001 / Story 2 #1 non-matching claims are
        # silently skipped, so the only remaining path is the IFC-922 default-group fallback.
        sso_groups = []

    if not sso_groups:
        default_name = config.SETTINGS.security.sso_user_default_group
        if not default_name:
            return
        log.info(
            "auth_groups.default_group_fallback_applied",
            provider_name=external_identity.provider_name,
            default_group=default_name,
        )
        sso_groups = [default_name]

    infrahub_groups = await NodeManager.query(
        db=db,
        schema=CoreAccountGroup,
        filters={"name__values": sso_groups},
        prefetch_relationships=True,
    )
    for group in infrahub_groups:
        members_rel = group.get_relationship(name="members")
        members = await members_rel.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
        if account.id in members:
            continue
        await members_rel.add(db=db, data=account)
        await members_rel.save(db=db)


async def _build_signin_result(*, db: InfrahubDatabase, account: Node) -> AuthResult:
    refresh_expires = datetime.now(tz=UTC) + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)
    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)

    groups, roles = await fetch_account_groups_and_roles(db=db, account_id=account.id)
    typed_account = cast("CoreAccount", account)

    return AuthResult(
        token=models.UserToken(access_token=access_token, refresh_token=refresh_token),
        account_id=account.id,
        account_name=typed_account.name.value,
        account_type=typed_account.account_type.value,
        session_id=session_id,
        groups=groups,
        roles=roles,
        kind=account.get_kind(),
    )


def generate_access_token(account_id: str, session_id: uuid.UUID) -> str:
    now = datetime.now(tz=UTC)

    access_expires = now + timedelta(seconds=config.SETTINGS.security.access_token_lifetime)
    access_data = {
        "sub": account_id,
        "iat": now,
        "nbf": now,
        "exp": access_expires,
        "fresh": False,
        "type": "access",
        "session_id": str(session_id),
    }
    access_token = jwt.encode(access_data, config.SETTINGS.security.secret_key, algorithm="HS256")
    return access_token


def generate_refresh_token(account_id: str, session_id: uuid.UUID, expiration: datetime) -> str:
    now = datetime.now(tz=UTC)

    refresh_data = {
        "sub": account_id,
        "iat": now,
        "nbf": now,
        "exp": expiration,
        "fresh": False,
        "type": "refresh",
        "session_id": str(session_id),
    }
    refresh_token = jwt.encode(refresh_data, config.SETTINGS.security.secret_key, algorithm="HS256")
    return refresh_token


async def authentication_token(
    db: InfrahubDatabase, jwt_token: str | None = None, api_key: str | None = None
) -> AccountSession:
    if api_key:
        return await validate_api_key(db=db, token=api_key)
    if jwt_token:
        return await validate_jwt_access_token(token=jwt_token)

    return AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE)


async def validate_jwt_access_token(token: str) -> AccountSession:
    try:
        payload = jwt.decode(token, config.SETTINGS.security.secret_key, algorithms=["HS256"])
        account_id = payload["sub"]
        session_id = payload["session_id"]
    except jwt.ExpiredSignatureError:
        raise AuthorizationError("Expired Signature") from None
    except Exception:
        raise AuthorizationError("Invalid token") from None

    if payload["type"] == "access":
        return AccountSession(account_id=account_id, session_id=session_id, auth_type=AuthType.JWT)

    raise AuthorizationError("Invalid token, current token is not an access token")


async def validate_jwt_refresh_token(db: InfrahubDatabase, token: str) -> models.RefreshTokenData:
    try:
        payload = jwt.decode(token, config.SETTINGS.security.secret_key, algorithms=["HS256"])
        account_id = payload["sub"]
        session_id = payload["session_id"]
    except jwt.ExpiredSignatureError:
        raise AuthorizationError("Expired Signature") from None
    except Exception:
        raise AuthorizationError("Invalid token") from None

    await validate_active_account(db=db, account_id=str(account_id))

    if payload["type"] == "refresh":
        return models.RefreshTokenData(account_id=account_id, session_id=session_id)

    raise AuthorizationError("Invalid token, current token is not a refresh token")


async def validate_api_key(db: InfrahubDatabase, token: str) -> AccountSession:
    account_id = await validate_token(token=token, db=db)
    if not account_id:
        raise AuthorizationError("Invalid token")

    await validate_active_account(db=db, account_id=str(account_id))

    return AccountSession(account_id=account_id, auth_type=AuthType.API)


async def invalidate_refresh_token(db: InfrahubDatabase, token_id: str) -> bool:
    refresh_token = await NodeManager.get_one(id=token_id, db=db)
    if refresh_token:
        await refresh_token.delete(db=db)
        return True
    return False


async def get_groups_from_provider(
    provider: SecurityOAuth2Settings | SecurityOIDCSettings, service: InfrahubServices, payload: dict, user_info: dict
) -> list[str]:
    if isinstance(provider, (SecurityOAuth2Google, SecurityOIDCGoogle)):
        # Poor man's workaround to fetch user groups from Google
        if provider.fetch_groups:
            groups_response = await service.http.get(
                f"{provider.cloudidentity_url}?query=member_key_id == '{user_info['email']}'",
                headers={"Authorization": f"{payload.get('token_type')} {payload.get('access_token')}"},
            )
            group_memberships = groups_response.json()
            if "memberships" in group_memberships:
                return [membership["groupKey"]["id"] for membership in group_memberships["memberships"]]

    return []


def safe_get_response_body(response: httpx.Response, raise_error_on_empty_body: bool = True) -> str | dict[str, Any]:
    """Safely extract response body from HTTP response. If the response body cannot be JSON parsed or is empty,
    it raises a GatewayError.

    Args:
        response: The HTTP response object
        raise_error_on_empty_body: Whether to raise an error if the response body is empty

    Returns:
        The response body as JSON dict if possible, otherwise as text

    Raises:
        GatewayError: When the response body cannot be parsed or is empty

    """
    # Try to parse as JSON first
    try:
        return response.json()
    except Exception as json_error:
        try:
            # Try to get as text
            text_body = response.text
            if not text_body.strip() and raise_error_on_empty_body:  # Check for empty or whitespace-only response
                log.error(
                    "Empty response body from authentication provider",
                    url=str(response.url),
                    status_code=response.status_code,
                )
                raise GatewayError(message="Authentication provider returned an empty response") from json_error
        except Exception:
            log.error(
                "Unable to read response body from authentication provider",
                url=str(response.url),
                status_code=response.status_code,
            )
            raise GatewayError(message="Unable to read response from authentication provider") from json_error

    # Here it means we got a text response but not JSON
    return text_body


def extract_auth_error_message(response_body: str | dict[str, Any], base_message: str) -> str:
    """Extract error message from OAuth 2.0/OIDC provider response following RFC 6749.

    Args:
        response_body: The response body from the authentication provider
        base_message: Base error message to use if no specific error is found

    Returns:
        Formatted error message with provider details if available

    """
    if not isinstance(response_body, dict):
        return base_message

    # RFC 6749 standard error response format
    error_description = response_body.get("error_description")
    error_code = response_body.get("error")

    if error_description:
        return f"{base_message}: {error_description}"
    if error_code:
        return f"{base_message}: {error_code}"

    return base_message


def validate_auth_response(response: httpx.Response, provider_type: str = "authentication") -> None:
    """Validate HTTP response from OAuth 2.0/OIDC provider and raise appropriate errors.

    Args:
        response: The HTTP response from the authentication provider
        provider_type: Type of provider for logging (e.g., "OAuth 2.0", "OIDC")

    Raises:
        GatewayError: When the response indicates an error or invalid state

    """
    # If the status code is successful, simply return
    if 200 <= response.status_code <= 299:
        # Verify that we can read the response body safely and it is not empty
        safe_get_response_body(response)
        return

    # Prepare variables with default values for logging
    response_body = safe_get_response_body(response, raise_error_on_empty_body=False)
    log_message: str = f"Unexpected response from {provider_type} provider"
    base_msg: str = "Unexpected response from authentication provider."

    # Handle specific HTTP status codes with appropriate error messages
    match response.status_code:
        case 400:
            log_message = f"Bad request to {provider_type} provider"
            base_msg = "Bad request to authentication provider. Please try again later or contact your administrator."

        case 401:
            log_message = f"Unauthorized request to {provider_type} provider"
            base_msg = (
                "Unauthorized request to authentication provider. Please try again later or contact your administrator."
            )

        case 403:
            log_message = f"Forbidden request to {provider_type} provider"
            base_msg = (
                "Access forbidden by authentication provider. Please try again later or contact your administrator."
            )

        case 404:
            log_message = f"Resource not found for {provider_type} provider"
            base_msg = (
                "Authentication provider endpoint not found. Please try again later or contact your administrator."
            )

        case 429:
            log_message = f"Rate limited by {provider_type} provider"
            base_msg = "Rate limited by authentication provider. Please try again later."

        case status_code if 500 <= status_code <= 599:
            log_message = f"Server error from {provider_type} provider"
            base_msg = "Authentication provider is experiencing server issues. Please try again later or contact your administrator."

    # Print proper log and raise gateway error
    log.error(log_message, url=str(response.url), status_code=response.status_code, body=response_body)
    error_msg = extract_auth_error_message(response_body, base_msg)
    raise GatewayError(message=error_msg)

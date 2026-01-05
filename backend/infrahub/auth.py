from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import bcrypt
import jwt
from pydantic import BaseModel

from infrahub import config, models
from infrahub.config import (
    SecurityOAuth2Google,
    SecurityOAuth2Settings,
    SecurityOIDCGoogle,
    SecurityOIDCSettings,
)
from infrahub.core.account import validate_token
from infrahub.core.constants import AccountStatus, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup, CoreGenericAccount
from infrahub.core.registry import registry
from infrahub.exceptions import AuthorizationError, GatewayError, NodeNotFoundError
from infrahub.log import get_logger

if TYPE_CHECKING:
    import httpx

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices

log = get_logger()


class AuthType(StrEnum):
    NONE = "none"
    JWT = "jwt"
    API = "api"


class AccountSession(BaseModel):
    authenticated: bool = True
    account_id: str
    session_id: str | None = None
    auth_type: AuthType

    @property
    def authenticated_by_jwt(self) -> bool:
        return self.auth_type == AuthType.JWT


class SSOStateCache(BaseModel):
    """Cache data stored during OAuth2/OIDC authorization flow.

    This model is used to store state information between the authorization
    request and the token exchange, including PKCE code_verifier when enabled.
    """

    final_url: str
    code_verifier: str | None = None


async def validate_active_account(db: InfrahubDatabase, account_id: str) -> None:
    account = await NodeManager.get_one(db=db, kind=CoreGenericAccount, id=account_id, raise_on_error=True)
    if account.status.value != AccountStatus.ACTIVE.value:
        raise AuthorizationError("This account has been deactivated")


async def authenticate_with_password(
    db: InfrahubDatabase, credentials: models.PasswordCredential, branch: str | None = None
) -> models.UserToken:
    selected_branch = await registry.get_branch(db=db, branch=branch)

    response: list[CoreGenericAccount] = await NodeManager.query(
        schema=InfrahubKind.GENERICACCOUNT,
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

    return models.UserToken(access_token=access_token, refresh_token=refresh_token)


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


async def signin_sso_account(db: InfrahubDatabase, account_name: str, sso_groups: list[str]) -> models.UserToken:
    account = await NodeManager.get_one_by_default_filter(db=db, id=account_name, kind=InfrahubKind.ACCOUNT)

    if not account:
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name=account_name, account_type="User", password=str(uuid.uuid4()))
        await account.save(db=db)

    if sso_groups:
        infrahub_groups = await NodeManager.query(
            db=db,
            schema=CoreAccountGroup,
            filters={"name__values": sso_groups},
            prefetch_relationships=True,
        )
        for group in infrahub_groups:
            members = await group.members.get_peers(db=db, branch_agnostic=True, peer_type=CoreAccount)
            if account.id not in members:
                await group.members.add(db=db, data=account)
                await group.members.save(db=db)

    now = datetime.now(tz=UTC)
    refresh_expires = now + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)
    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)
    return models.UserToken(access_token=access_token, refresh_token=refresh_token)


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


async def invalidate_refresh_token(db: InfrahubDatabase, token_id: str) -> None:
    refresh_token = await NodeManager.get_one(id=token_id, db=db)
    if refresh_token:
        await refresh_token.delete(db=db)


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

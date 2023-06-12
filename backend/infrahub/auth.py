from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Optional

import bcrypt
import jwt
from pydantic import BaseModel
from starlette import authentication as auth
from starlette.authentication import AuthenticationError

from infrahub import config, models
from infrahub.core import get_branch
from infrahub.core.account import get_account, validate_token
from infrahub.core.manager import NodeManager
from infrahub.exceptions import AuthorizationError, NodeNotFound

if TYPE_CHECKING:
    from neo4j import AsyncSession
    from starlette.requests import HTTPConnection

# from ..datatypes import AuthResult
# from ..exceptions import InvalidCredentials


class AccountSession(BaseModel):
    authenticated: bool = True
    account_id: str
    role: str = "read-only"

    @property
    def read_only(self) -> bool:
        return self.role == "read-only"


async def authenticate_with_password(
    session: AsyncSession, credentials: models.PasswordCredential, branch: Optional[str] = None
) -> models.UserToken:
    selected_branch = await get_branch(session=session, branch=branch)
    response = await NodeManager.query(
        schema="Account",
        session=session,
        branch=selected_branch,
        filters={"name__value": credentials.username},
        limit=1,
    )
    if not response:
        raise NodeNotFound(
            branch_name=selected_branch.name,
            node_type="Account",
            identifier=credentials.username,
            message="That login user doesn't exist in the system",
        )
    user = response[0]
    valid_credentials = bcrypt.checkpw(credentials.password.encode("UTF-8"), user.password.value.encode("UTF-8"))
    if not valid_credentials:
        raise AuthorizationError("Incorrect password")
    now = datetime.now(tz=timezone.utc)
    expires = now + timedelta(seconds=config.SETTINGS.security.access_token_lifetime)

    access_data = {
        "sub": user.id,
        "iat": now,
        "nbf": now,
        "exp": expires,
        "fresh": False,
        "type": "access",
        "user_claims": {"role": user.role.value},
    }
    access_token = jwt.encode(access_data, config.SETTINGS.security.secret_key, algorithm="HS256")
    return models.UserToken(access_token=access_token)


async def authentication_token(
    session: AsyncSession, jwt_token: Optional[str] = None, api_key: Optional[str] = None
) -> AccountSession:
    if api_key:
        return await validate_api_key(session=session, token=api_key)
    if jwt_token:
        return await validate_jwt_access_token(token=jwt_token)

    return AccountSession(authenticated=False, account_id="anonymous")


async def validate_jwt_access_token(token: str) -> AccountSession:
    try:
        payload = jwt.decode(token, config.SETTINGS.security.secret_key, algorithms=["HS256"])
        user_id = payload["sub"]
        role = payload["user_claims"]["role"]
    except jwt.ExpiredSignatureError:
        raise AuthorizationError("Expired Signature") from None
    except Exception:
        raise AuthorizationError("Invalid token") from None

    if payload["type"] == "access":
        return AccountSession(account_id=user_id, role=role)

    raise AuthorizationError("Invalid token, current token is not an access token")


async def validate_api_key(session: AsyncSession, token: str) -> AccountSession:
    account_id, role = await validate_token(token=token, session=session)
    if not account_id:
        raise AuthorizationError("Invalid token")

    return AccountSession(account_id=account_id, role=role)


def _validate_is_admin(account_session: AccountSession) -> None:
    if account_session.role != "admin":
        raise PermissionError("You are not authorized to perform this operation")


def _validate_update_account(account_session: AccountSession, node_id: str, fields: List[str]) -> None:
    if account_session.role == "admin":
        return

    if account_session.account_id != node_id:
        # A regular account is not allowed to modify another account
        raise PermissionError("You are not allowed to modify this account")

    allowed_fields = ["description", "label", "password"]
    for field in fields:
        if field not in allowed_fields:
            raise PermissionError(f"You are not allowed to modify '{field}'")


def validate_mutation_permissions(operation: str, account_session: AccountSession) -> None:
    if config.SETTINGS.experimental_features.ignore_authentication_requirements:
        # This feature will later be removed.
        return

    validation_map: Dict[str, Callable[[AccountSession], None]] = {
        "AccountCreate": _validate_is_admin,
        "AccountDelete": _validate_is_admin,
    }
    if validator := validation_map.get(operation):
        validator(account_session)


def validate_mutation_permissions_update_node(
    operation: str, node_id: str, account_session: AccountSession, fields: List[str]
) -> None:
    if config.SETTINGS.experimental_features.ignore_authentication_requirements:
        # This feature will later be removed.
        return

    validation_map: Dict[str, Callable[[AccountSession, str, List[str]], None]] = {
        "AccountUpdate": _validate_update_account,
    }

    if validator := validation_map.get(operation):
        validator(account_session, node_id, fields)


# Code copied from https://github.com/florimondmanca/starlette-auth-toolkit/


class InvalidCredentials(AuthenticationError):
    def __init__(
        self,
        message: str = "Could not authenticate with the provided credentials",
    ):
        super().__init__(message)


class AuthBackend(auth.AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):  # -> AuthResult:
        raise NotImplementedError


class _BaseSchemeAuth(AuthBackend):
    scheme: str

    def get_credentials(self, conn: HTTPConnection) -> Optional[str]:
        if "Authorization" not in conn.headers:
            return None

        authorization = conn.headers.get("Authorization")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() != self.scheme.lower():
            return None

        return credentials

    def parse_credentials(self, credentials: str) -> List[str]:
        return [credentials]

    verify: Callable[..., Awaitable[Optional[auth.BaseUser]]]

    async def authenticate(self, conn: HTTPConnection):
        credentials = self.get_credentials(conn)
        if credentials is None:
            return None

        parts = self.parse_credentials(credentials)

        async with conn.app.state.db.session(database=config.SETTINGS.database.database) as session:
            user = await self.verify(session=session, token=parts[0])

        if user is None:
            raise InvalidCredentials

        return auth.AuthCredentials(["authenticated"]), user


# class BaseBasicAuth(_BaseSchemeAuth):
#     scheme = "Basic"

#     def parse_credentials(self, credentials: str) -> typing.List[str]:
#         try:
#             decoded_credentials = base64.b64decode(credentials).decode("ascii")
#         except (ValueError, UnicodeDecodeError, binascii.Error):
#             raise InvalidCredentials

#         try:
#             username, password = decoded_credentials.split(":")
#         except ValueError:
#             raise InvalidCredentials

#         return [username, password]

#     async def find_user(self, username: str) -> typing.Optional[auth.BaseUser]:
#         raise NotImplementedError

#     async def verify_password(self, user: auth.BaseUser, password: str) -> bool:
#         raise NotImplementedError

#     async def verify(
#         self, username: str, password: str
#     ) -> typing.Optional[auth.BaseUser]:
#         user = await self.find_user(username=username)

#         if user is None:
#             return None

#         valid = await self.verify_password(user, password)
#         if not valid:
#             return None

#         return user


class BaseTokenAuth(_BaseSchemeAuth):
    scheme = "Token"

    def parse_credentials(self, credentials: str) -> List[str]:
        token = credentials
        return [token]

    async def verify(self, session: AsyncSession, token: str) -> Optional[auth.BaseUser]:
        account_name, _ = await validate_token(session=session, token=token)
        if account_name:
            account = await get_account(session=session, account=account_name)
            return account

        return False

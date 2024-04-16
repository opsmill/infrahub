from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

import bcrypt
import jwt
from opentelemetry import trace
from pydantic.v1 import BaseModel

from infrahub import config, models
from infrahub.core.account import validate_token
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.exceptions import AuthorizationError, NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

# from ..datatypes import AuthResult


class AuthType(str, Enum):
    NONE = "none"
    JWT = "jwt"
    API = "api"


class AccountSession(BaseModel):
    authenticated: bool = True
    account_id: str
    session_id: Optional[str] = None
    role: str = "read-only"
    auth_type: AuthType

    @property
    def read_only(self) -> bool:
        return self.role == "read-only"


async def authenticate_with_password(
    db: InfrahubDatabase, credentials: models.PasswordCredential, branch: Optional[str] = None
) -> models.UserToken:
    selected_branch = await registry.get_branch(db=db, branch=branch)
    response = await NodeManager.query(
        schema=InfrahubKind.ACCOUNT,
        db=db,
        branch=selected_branch,
        filters={"name__value": credentials.username},
        limit=1,
    )
    if not response:
        raise NodeNotFoundError(
            branch_name=selected_branch.name,
            node_type=InfrahubKind.ACCOUNT,
            identifier=credentials.username,
            message="That login user doesn't exist in the system",
        )
    account = response[0]
    valid_credentials = bcrypt.checkpw(credentials.password.encode("UTF-8"), account.password.value.encode("UTF-8"))
    if not valid_credentials:
        raise AuthorizationError("Incorrect password")

    now = datetime.now(tz=timezone.utc)

    refresh_expires = now + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)
    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, role=account.role.value.value, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)

    return models.UserToken(access_token=access_token, refresh_token=refresh_token)


async def create_db_refresh_token(db: InfrahubDatabase, account_id: str, expiration: datetime) -> uuid.UUID:
    obj = await Node.init(db=db, schema=InfrahubKind.REFRESHTOKEN)
    await obj.new(
        db=db,
        account=account_id,
        expiration=expiration.isoformat(),
    )
    await obj.save(db=db)
    return uuid.UUID(obj.id)


async def create_fresh_access_token(
    db: InfrahubDatabase, refresh_data: models.RefreshTokenData
) -> models.AccessTokenResponse:
    selected_branch = await registry.get_branch(db=db)

    refresh_token = await NodeManager.get_one(
        id=str(refresh_data.session_id),
        db=db,
    )
    if not refresh_token:
        raise AuthorizationError("The provided refresh token has been invalidated in the database")

    account = await NodeManager.get_one(
        id=refresh_data.account_id,
        db=db,
    )
    if not account:
        raise NodeNotFoundError(
            branch_name=selected_branch.name,
            node_type="Account",
            identifier=refresh_data.account_id,
            message="That login user doesn't exist in the system",
        )

    access_token = generate_access_token(
        account_id=account.id, role=account.role.value.value, session_id=refresh_data.session_id
    )

    return models.AccessTokenResponse(access_token=access_token)


def generate_access_token(account_id: str, role: str, session_id: uuid.UUID) -> str:
    now = datetime.now(tz=timezone.utc)

    access_expires = now + timedelta(seconds=config.SETTINGS.security.access_token_lifetime)
    access_data = {
        "sub": account_id,
        "iat": now,
        "nbf": now,
        "exp": access_expires,
        "fresh": False,
        "type": "access",
        "session_id": str(session_id),
        "user_claims": {"role": role},
    }
    access_token = jwt.encode(access_data, config.SETTINGS.security.secret_key, algorithm="HS256")
    return access_token


def generate_refresh_token(account_id: str, session_id: uuid.UUID, expiration: datetime) -> str:
    now = datetime.now(tz=timezone.utc)

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


@trace.get_tracer(__name__).start_as_current_span("authentication_token")
async def authentication_token(
    db: InfrahubDatabase, jwt_token: Optional[str] = None, api_key: Optional[str] = None
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
        role = payload["user_claims"]["role"]
        session_id = payload["session_id"]
    except jwt.ExpiredSignatureError:
        raise AuthorizationError("Expired Signature") from None
    except Exception:
        raise AuthorizationError("Invalid token") from None

    if payload["type"] == "access":
        return AccountSession(account_id=account_id, role=role, session_id=session_id, auth_type=AuthType.JWT)

    raise AuthorizationError("Invalid token, current token is not an access token")


def validate_jwt_refresh_token(token: str) -> models.RefreshTokenData:
    try:
        payload = jwt.decode(token, config.SETTINGS.security.secret_key, algorithms=["HS256"])
        account_id = payload["sub"]
        session_id = payload["session_id"]
    except jwt.ExpiredSignatureError:
        raise AuthorizationError("Expired Signature") from None
    except Exception:
        raise AuthorizationError("Invalid token") from None

    if payload["type"] == "refresh":
        return models.RefreshTokenData(account_id=account_id, session_id=session_id)

    raise AuthorizationError("Invalid token, current token is not a refresh token")


async def validate_api_key(db: InfrahubDatabase, token: str) -> AccountSession:
    account_id, role = await validate_token(token=token, db=db)
    if not account_id:
        raise AuthorizationError("Invalid token")

    return AccountSession(account_id=account_id, role=role, auth_type=AuthType.API)


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
    validation_map: Dict[str, Callable[[AccountSession], None]] = {
        "AccountCreate": _validate_is_admin,
        "AccountDelete": _validate_is_admin,
    }
    if validator := validation_map.get(operation):
        validator(account_session=account_session)


def validate_mutation_permissions_update_node(
    operation: str, node_id: str, account_session: AccountSession, fields: List[str]
) -> None:
    validation_map: Dict[str, Callable[[AccountSession, str, List[str]], None]] = {
        "AccountUpdate": _validate_update_account,
    }

    if validator := validation_map.get(operation):
        validator(account_session=account_session, node_id=node_id, fields=fields)


async def invalidate_refresh_token(db: InfrahubDatabase, token_id: str) -> None:
    refresh_token = await NodeManager.get_one(
        id=token_id,
        db=db,
    )
    if refresh_token:
        await refresh_token.delete(db=db)

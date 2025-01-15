from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

import bcrypt
import jwt
from pydantic import BaseModel

from infrahub import config, models
from infrahub.core.account import validate_token
from infrahub.core.constants import AccountStatus, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreAccountGroup
from infrahub.core.registry import registry
from infrahub.exceptions import AuthorizationError, NodeNotFoundError

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreGenericAccount
    from infrahub.database import InfrahubDatabase


class AuthType(str, Enum):
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


async def validate_active_account(db: InfrahubDatabase, account_id: str) -> None:
    account: CoreGenericAccount = await NodeManager.get_one(db=db, id=account_id, raise_on_error=True)
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

    now = datetime.now(tz=timezone.utc)
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

    account: CoreGenericAccount | None = await NodeManager.get_one(id=refresh_data.account_id, db=db)
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

    now = datetime.now(tz=timezone.utc)
    refresh_expires = now + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)
    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)
    return models.UserToken(access_token=access_token, refresh_token=refresh_token)


def generate_access_token(account_id: str, session_id: uuid.UUID) -> str:
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

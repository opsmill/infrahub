from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, Optional

from fastapi import Depends, Query, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic.v1 import BaseModel

from infrahub import config
from infrahub.auth import AccountSession, authentication_token, validate_jwt_access_token, validate_jwt_refresh_token
from infrahub.core import get_branch
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase  # noqa: TCH001
from infrahub.exceptions import AuthorizationError, PermissionDeniedError

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.models import RefreshTokenData

jwt_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-INFRAHUB-KEY", auto_error=False)


async def cookie_auth_scheme(request: Request) -> Optional[str]:
    return request.cookies.get("access_token")  # Replace with the actual name of your JWT cookie


class BranchParams(BaseModel):
    branch: Branch
    at: Timestamp
    rebase: bool

    class Config:
        arbitrary_types_allowed = True


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session = request.app.state.db.session(database=config.SETTINGS.database.database_name)
    try:
        yield session
    finally:
        await session.close()


async def get_db(request: Request) -> InfrahubDatabase:
    return request.app.state.db.start_session()


async def get_access_token(
    request: Request,
    jwt_header: HTTPAuthorizationCredentials = Depends(jwt_scheme),
) -> AccountSession:
    if jwt_header:
        return await validate_jwt_access_token(token=jwt_header.credentials)
    if token := request.cookies.get("access_token"):
        return await validate_jwt_access_token(token=token)

    raise AuthorizationError("A JWT access token is required to perform this operation.")


async def get_refresh_token(
    request: Request, jwt_header: Optional[HTTPAuthorizationCredentials] = Depends(jwt_scheme)
) -> RefreshTokenData:
    token = None

    # Check for token in header
    if jwt_header:
        token = jwt_header.credentials

    # If no auth header, try to get the token from the cookie
    if not token:
        token = request.cookies.get("refresh_token")

    # If still no token, raise an error
    if not token:
        raise AuthorizationError("A JWT refresh token is required to perform this operation.")

    return validate_jwt_refresh_token(token=token)


async def get_branch_params(
    db: InfrahubDatabase = Depends(get_db),
    branch_name: Optional[str] = Query(None, alias="branch", description="Name of the branch to use for the query"),
    at: Optional[str] = Query(None, description="Time to use for the query, in absolute or relative format"),
    rebase: bool = Query(
        False, description="Temporarily rebase the current branch with the main branch for the duration of the query"
    ),
) -> BranchParams:
    branch = await get_branch(db=db, branch=branch_name)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    return BranchParams(branch=branch, at=at, rebase=rebase)


async def get_branch_dep(
    db: InfrahubDatabase = Depends(get_db),
    branch_name: Optional[str] = Query(None, alias="branch", description="Name of the branch to use for the query"),
) -> Branch:
    return await get_branch(db=db, branch=branch_name)


async def get_current_user(
    request: Request,
    jwt_header: HTTPAuthorizationCredentials = Depends(jwt_scheme),
    db: InfrahubDatabase = Depends(get_db),
    api_key: str = Depends(api_key_scheme),
) -> AccountSession:
    """Return current user"""
    jwt_token = None
    if jwt_header:
        jwt_token = jwt_header.credentials

    if not jwt_token:
        jwt_token = request.cookies.get("access_token")

    account_session = await authentication_token(db=db, jwt_token=jwt_token, api_key=api_key)

    if account_session.authenticated or request.url.path.startswith("/graphql"):
        return account_session

    if config.SETTINGS.main.allow_anonymous_access and request.method.lower() in ["get", "options"]:
        return account_session

    if request.method.lower() == "post" and account_session.read_only:
        raise PermissionDeniedError("You are not allowed to perform this operation")

    raise AuthorizationError("Authentication is required")

from typing import Optional

from fastapi import Depends, Query, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from neo4j import AsyncSession
from pydantic import BaseModel

from infrahub import config
from infrahub.auth import (
    AccountSession,
    authentication_token,
    validate_jwt_refresh_token,
)
from infrahub.core import get_branch
from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import AuthorizationError, PermissionDeniedError
from infrahub.models import RefreshTokenData

jwt_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-INFRAHUB-KEY", auto_error=False)


class BranchParams(BaseModel):
    branch: Branch
    at: Timestamp
    rebase: bool

    class Config:
        arbitrary_types_allowed = True


async def get_session(request: Request) -> AsyncSession:
    session = request.app.state.db.session(database=config.SETTINGS.database.database)
    try:
        yield session
    finally:
        await session.close()


async def get_refresh_token(
    jwt_header: HTTPAuthorizationCredentials = Depends(jwt_scheme),
) -> RefreshTokenData:
    if not jwt_header:
        raise AuthorizationError("A JWT refresh token is required to perform this operation.")
    return validate_jwt_refresh_token(token=jwt_header.credentials)


async def get_branch_params(
    session: AsyncSession = Depends(get_session),
    branch_name: Optional[str] = Query(None, alias="branch", description="Name of the branch to use for the query"),
    at: Optional[str] = Query(None, description="Time to use for the query, in absolute or relative format"),
    rebase: bool = Query(
        False, description="Temporarily rebase the current branch with the main branch for the duration of the query"
    ),
) -> BranchParams:
    branch = await get_branch(session=session, branch=branch_name)
    branch.ephemeral_rebase = rebase
    at = Timestamp(at)

    return BranchParams(branch=branch, at=at, rebase=rebase)


async def get_branch_dep(
    session: AsyncSession = Depends(get_session),
    branch_name: Optional[str] = Query(None, alias="branch", description="Name of the branch to use for the query"),
) -> Branch:
    return await get_branch(session=session, branch=branch_name)


async def get_current_user(
    request: Request,
    jwt_header: HTTPAuthorizationCredentials = Depends(jwt_scheme),
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(api_key_scheme),
) -> AccountSession:
    """Return current user"""
    jwt_token = None
    if jwt_header:
        jwt_token = jwt_header.credentials

    account_session = await authentication_token(session=session, jwt_token=jwt_token, api_key=api_key)

    if account_session.authenticated or request.url.path.startswith("/graphql"):
        return account_session

    if config.SETTINGS.experimental_features.ignore_authentication_requirements:
        # This feature will later be removed.
        return account_session

    if config.SETTINGS.main.allow_anonymous_access and request.method.lower() in ["get", "options"]:
        return account_session

    if request.method.lower() == "post" and account_session.read_only:
        raise PermissionDeniedError("You are not allowed to perform this operation")

    raise AuthorizationError("Authentication is required")

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from fastapi import Depends, Query, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from infrahub import config
from infrahub.auth import AccountSession, authentication_token, validate_jwt_access_token, validate_jwt_refresh_token
from infrahub.context import InfrahubContext
from infrahub.core.branch import Branch  # noqa: TC001
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase  # noqa: TC001
from infrahub.exceptions import AuthorizationError
from infrahub.permissions import PermissionManager

if TYPE_CHECKING:
    from neo4j import AsyncSession

    from infrahub.models import RefreshTokenData

jwt_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-INFRAHUB-KEY", auto_error=False)


async def cookie_auth_scheme(request: Request) -> str | None:
    return request.cookies.get("access_token")  # Replace with the actual name of your JWT cookie


class BranchParams(BaseModel):
    branch: Branch
    at: Timestamp

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session = request.app.state.db.session(database=config.SETTINGS.database.database_name)
    try:
        yield session
    finally:
        await session.close()


async def get_db(request: Request) -> InfrahubDatabase:
    return request.app.state.db.start_session()


async def get_access_token(
    request: Request, jwt_header: HTTPAuthorizationCredentials = Depends(jwt_scheme)
) -> AccountSession:
    if jwt_header:
        return await validate_jwt_access_token(token=jwt_header.credentials)
    if token := request.cookies.get("access_token"):
        return await validate_jwt_access_token(token=token)

    raise AuthorizationError("A JWT access token is required to perform this operation.")


async def get_refresh_token(
    request: Request,
    db: InfrahubDatabase = Depends(get_db),
    jwt_header: HTTPAuthorizationCredentials | None = Depends(jwt_scheme),
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

    return await validate_jwt_refresh_token(db=db, token=token)


async def get_branch_params(
    db: InfrahubDatabase = Depends(get_db),
    branch_name: str | None = Query(None, alias="branch", description="Name of the branch to use for the query"),
    at: str | None = Query(None, description="Time to use for the query, in absolute or relative format"),
) -> BranchParams:
    branch = await registry.get_branch(db=db, branch=branch_name)

    return BranchParams(branch=branch, at=Timestamp(at))


async def get_branch_dep(
    db: InfrahubDatabase = Depends(get_db),
    branch_name: str | None = Query(None, alias="branch", description="Name of the branch to use for the query"),
) -> Branch:
    return await registry.get_branch(db=db, branch=branch_name)


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

    if (
        account_session.authenticated
        or request.url.path.startswith("/graphql")
        or (config.SETTINGS.main.allow_anonymous_access and request.method.lower() in ["get", "options"])
    ):
        return account_session

    raise AuthorizationError("Authentication is required")


async def get_permission_manager(
    db: InfrahubDatabase = Depends(get_db),
    branch_params: BranchParams = Depends(get_branch_params),
    account_session: AccountSession = Depends(get_current_user),
) -> PermissionManager:
    """Return a `PermissionManager` for an account session based on a branch."""
    permission_manager = PermissionManager(account_session=account_session)
    await permission_manager.load_permissions(db=db, branch=branch_params.branch)

    return permission_manager


async def get_context(
    branch: Branch = Depends(get_branch_dep),
    account_session: AccountSession = Depends(get_current_user),
) -> InfrahubContext:
    return InfrahubContext.init(branch=branch, account=account_session)

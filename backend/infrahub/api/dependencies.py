from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from neo4j import AsyncSession

from infrahub import config
from infrahub.auth import validate_authentication_token

jwt_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-INFRAHUB-KEY", auto_error=False)


async def get_session(request: Request) -> AsyncSession:
    session = request.app.state.db.session(database=config.SETTINGS.database.database)
    try:
        yield session
    finally:
        await session.close()


async def get_current_user(
    jwt_token: HTTPAuthorizationCredentials = Depends(jwt_scheme),
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(api_key_scheme),
) -> str:
    """Return current user"""
    if jwt_token:
        return await validate_authentication_token(session=session, jwt_token=jwt_token.credentials, api_key=api_key)

    return await validate_authentication_token(session=session, api_key=api_key)

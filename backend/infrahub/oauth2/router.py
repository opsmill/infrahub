import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from infrahub import config, models
from infrahub.api.dependencies import get_db
from infrahub.auth import create_db_refresh_token, generate_access_token, generate_refresh_token
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

router = APIRouter(prefix="/oauth2")


@router.get("/{provider}/authorize")
def authorize(request: Request, provider: str) -> Response:
    if os.getenv("FRONTEND_REDIRECT") == "true":
        return JSONResponse(content={"url": request.auth.clients[provider].authorization_url(request)})
    return request.auth.clients[provider].authorization_redirect(request)


@router.get("/{provider}/token")
async def token(
    request: Request, provider: str, response: Response, db: InfrahubDatabase = Depends(get_db)
) -> models.UserToken:
    token_data = await request.auth.clients[provider].token_data(request)
    account = await NodeManager.get_one_by_default_filter(db=db, id=token_data["name"], kind=InfrahubKind.ACCOUNT)

    if not account:
        account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await account.new(db=db, name=token_data["name"], account_type="User", role="admin", password=str(uuid4()))
        await account.save(db=db)

    now = datetime.now(tz=timezone.utc)
    refresh_expires = now + timedelta(seconds=config.SETTINGS.security.refresh_token_lifetime)
    session_id = await create_db_refresh_token(db=db, account_id=account.id, expiration=refresh_expires)
    access_token = generate_access_token(account_id=account.id, role=account.role.value.value, session_id=session_id)
    refresh_token = generate_refresh_token(account_id=account.id, session_id=session_id, expiration=refresh_expires)
    user_token = models.UserToken(access_token=access_token, refresh_token=refresh_token)

    response.set_cookie(
        "access_token", user_token.access_token, httponly=True, max_age=config.SETTINGS.security.access_token_lifetime
    )
    response.set_cookie(
        "refresh_token",
        user_token.refresh_token,
        httponly=True,
        max_age=config.SETTINGS.security.refresh_token_lifetime,
    )

    return user_token

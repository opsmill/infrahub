import json
import os
import random
import re
import string
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi_oauth2.core import OAuth2Core
from fastapi_oauth2.exceptions import OAuth2AuthenticationError, OAuth2InvalidRequestError
from oauthlib.oauth2 import OAuth2Error
from social_core.exceptions import AuthException

from infrahub import config, models
from infrahub.api.dependencies import get_db
from infrahub.auth import create_db_refresh_token, generate_access_token, generate_refresh_token
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

log = get_logger()
router = APIRouter(prefix="/oauth2")


def get_redirect_url(request: Request) -> str:
    default_redirect = f"{request.base_url}oauth2/google-oauth2/token"
    return os.getenv("REDIRECT_URL") or default_redirect


@router.get("/{provider}/authorize")
def authorize(request: Request, provider: str) -> Response:
    auth_provider = request.auth.clients[provider]
    state = "".join([random.choice(string.ascii_letters) for _ in range(32)])
    auth_provider._state = state
    oauth2_query_params = {"state": state, "scope": auth_provider.scope, "redirect_uri": get_redirect_url(request)}
    oauth2_query_params.update(request.query_params)

    url = str(
        auth_provider._oauth_client.prepare_request_uri(
            auth_provider._authorization_endpoint,
            **oauth2_query_params,
        )
    )

    if os.getenv("FRONTEND_REDIRECT") == "true":
        return JSONResponse(content={"url": url})
    return RedirectResponse(url=url)


async def parse_token(request: Request, core: OAuth2Core) -> dict:
    if not request.query_params.get("code"):
        raise OAuth2InvalidRequestError(400, "'code' parameter was not found in callback request")
    if not request.query_params.get("state"):
        raise OAuth2InvalidRequestError(400, "'state' parameter was not found in callback request")
    if request.query_params.get("state") != core._state:
        raise OAuth2InvalidRequestError(400, "'state' parameter does not match")

    redirect_uri = get_redirect_url(request)
    scheme = "http" if request.auth.http else "https"
    authorization_response = re.sub(r"^https?", scheme, str(request.url))

    oauth2_query_params = {
        "redirect_url": redirect_uri,
        "client_secret": core.client_secret,
        "authorization_response": authorization_response,
    }
    oauth2_query_params.update(request.query_params)

    token_url, headers, content = core._oauth_client.prepare_token_request(
        core._token_endpoint,
        **oauth2_query_params,
    )

    headers.update({"Accept": "application/json"})
    auth = httpx.BasicAuth(core.client_id, core.client_secret)
    async with httpx.AsyncClient(auth=auth) as session:
        try:
            response = await session.post(token_url, headers=headers, content=content)
            if response.status_code == 401:
                content = re.sub(r"client_id=[^&]+", "", content)
                response = await session.post(token_url, headers=headers, content=content)
            core._oauth_client.parse_request_body_response(json.dumps(response.json()))
            return core.standardize(core.backend.user_data(core.access_token))
        except (OAuth2Error, httpx.HTTPError) as e:
            raise OAuth2InvalidRequestError(400, str(e))
        except (AuthException, Exception) as e:
            raise OAuth2AuthenticationError(401, str(e))


@router.get("/another")
async def token2(request: Request, response: Response, db: InfrahubDatabase = Depends(get_db)) -> models.UserToken:
    """Temporary test to validate that redirecations work"""
    auth_provider = request.auth.clients["google-oauth2"]

    # token_data = await request.auth.clients["google-oauth2"].token_data(request)
    token_data = await parse_token(request=request, core=auth_provider)
    account = await NodeManager.get_one_by_default_filter(db=db, id=token_data["name"], kind=InfrahubKind.ACCOUNT)
    log.info("I found another")
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


@router.get("/{provider}/token")
async def token(
    request: Request, provider: str, response: Response, db: InfrahubDatabase = Depends(get_db)
) -> models.UserToken:
    log.info("Original URL")

    auth_provider = request.auth.clients["google-oauth2"]

    # token_data = await request.auth.clients["google-oauth2"].token_data(request)
    token_data = await parse_token(request=request, core=auth_provider)
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

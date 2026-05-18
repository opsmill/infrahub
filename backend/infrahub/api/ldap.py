from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from infrahub import config, models
from infrahub.api.dependencies import get_db
from infrahub.workers.dependencies import get_ldap_auth_service

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.ldap_auth.service import LDAPAuthService


router = APIRouter(prefix="/auth/ldap")


class LDAPCredentials(BaseModel):
    username: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., min_length=1, repr=False)


class EnterpriseRequiredResponse(BaseModel):
    error_code: str = Field("ENTERPRISE_REQUIRED")
    feature: str
    message: str | None = None


class LDAPCollisionResponse(BaseModel):
    error_code: str = Field("LDAP_ACCOUNT_COLLISION")
    account_name: str
    message: str | None = None


class LDAPAuthErrorResponse(BaseModel):
    error_code: str
    message: str | None = None


@router.post(
    "/login",
    response_model=models.UserToken,
    responses={
        401: {"model": LDAPAuthErrorResponse, "description": "Authentication failed."},
        403: {"model": EnterpriseRequiredResponse, "description": "Enterprise runtime not active."},
        409: {"model": LDAPCollisionResponse, "description": "Username collides with an existing local-only account."},
        502: {"model": LDAPAuthErrorResponse, "description": "LDAP directory unavailable."},
    },
)
async def login_ldap(
    credentials: LDAPCredentials, response: Response, db: InfrahubDatabase = Depends(get_db)
) -> models.UserToken:
    ldap_service: LDAPAuthService = get_ldap_auth_service()
    auth_result = await ldap_service.authenticate(db=db, username=credentials.username, password=credentials.password)
    response.set_cookie(
        "access_token",
        auth_result.token.access_token,
        httponly=True,
        max_age=config.SETTINGS.security.access_token_lifetime,
    )
    response.set_cookie(
        "refresh_token",
        auth_result.token.refresh_token,
        httponly=True,
        max_age=config.SETTINGS.security.refresh_token_lifetime,
    )
    return auth_result.token

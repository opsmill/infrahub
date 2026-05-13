from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from infrahub import config, models
from infrahub.api.dependencies import get_db
from infrahub.exceptions import (
    EnterpriseRequiredError,
    LDAPAuthenticationError,
    LDAPCollisionError,
    LDAPDirectoryUnavailableError,
)
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
) -> models.UserToken | JSONResponse:
    ldap_service: LDAPAuthService = get_ldap_auth_service()
    try:
        auth_result = await ldap_service.authenticate(
            db=db, username=credentials.username, password=credentials.password
        )
    except EnterpriseRequiredError as exc:
        return JSONResponse(
            status_code=403,
            content={"error_code": "ENTERPRISE_REQUIRED", "feature": exc.feature, "message": exc.message},
        )
    except LDAPCollisionError as exc:
        return JSONResponse(
            status_code=409,
            content={"error_code": "LDAP_ACCOUNT_COLLISION", "account_name": exc.account_name, "message": exc.message},
        )
    except LDAPDirectoryUnavailableError as exc:
        return JSONResponse(
            status_code=502, content={"error_code": "LDAP_DIRECTORY_UNAVAILABLE", "message": exc.message}
        )
    except LDAPAuthenticationError as exc:
        # Intentional: every authn failure (wrong password, unknown user, disabled account,
        # ambiguous lookup via LDAPLookupError) collapses into one envelope so the response
        # cannot be used to enumerate accounts. Do not split this branch.
        return JSONResponse(status_code=401, content={"error_code": "AUTHENTICATION_FAILED", "message": exc.message})

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

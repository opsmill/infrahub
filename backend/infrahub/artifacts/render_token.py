"""Short-lived tokens that let an external engine return the result of one render request."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

import jwt
from pydantic import BaseModel, ValidationError

from infrahub import config
from infrahub.exceptions import AuthorizationError

RENDER_TOKEN_TYPE = "render"
RENDER_TOKEN_ALGORITHM = "HS256"


class RenderTokenClaims(BaseModel):
    render_id: str
    artifact_id: str
    branch: str


def mint_render_token(render_id: str, artifact_id: str, branch: str, deadline: datetime) -> str:
    claims = {
        "type": RENDER_TOKEN_TYPE,
        "render_id": render_id,
        "artifact_id": artifact_id,
        "branch": branch,
        "exp": deadline,
    }
    return jwt.encode(claims, config.SETTINGS.security.secret_key, algorithm=RENDER_TOKEN_ALGORITHM)


def validate_render_token(token: str) -> RenderTokenClaims:
    """Return the claims of a valid render token.

    Raises:
        AuthorizationError: When the signature is bad, the token is expired, it is not a render token or a claim is missing.

    """
    try:
        payload = jwt.decode(
            token,
            config.SETTINGS.security.secret_key,
            algorithms=[RENDER_TOKEN_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthorizationError("Expired render token") from None
    except jwt.InvalidTokenError:
        raise AuthorizationError("Invalid render token") from None

    if payload.get("type") != RENDER_TOKEN_TYPE:
        raise AuthorizationError("Invalid token, current token is not a render token")

    try:
        return RenderTokenClaims.model_validate(payload)
    except ValidationError:
        raise AuthorizationError("Invalid render token, a claim is missing") from None

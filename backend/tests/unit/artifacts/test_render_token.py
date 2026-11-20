import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from infrahub import config
from infrahub.artifacts.render_token import RenderTokenClaims, mint_render_token, validate_render_token
from infrahub.auth.auth import generate_access_token, validate_jwt_access_token
from infrahub.exceptions import AuthorizationError

SECRET = "render-token-test-secret-0123456789abcdef"


@pytest.fixture(autouse=True)
def secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.security, "secret_key", SECRET)


def _future() -> datetime:
    return datetime.now(tz=UTC) + timedelta(minutes=10)


def test_round_trip_returns_claims() -> None:
    token = mint_render_token(render_id="r1", artifact_id="a1", branch="main", deadline=_future())

    assert validate_render_token(token) == RenderTokenClaims(render_id="r1", artifact_id="a1", branch="main")


def test_bad_signature_is_refused() -> None:
    token = jwt.encode(
        {"type": "render", "render_id": "r1", "artifact_id": "a1", "branch": "main", "exp": _future()},
        "another-secret-0123456789abcdef0123456789",
        algorithm="HS256",
    )

    with pytest.raises(AuthorizationError, match=r"^Invalid render token$"):
        validate_render_token(token)


def test_expired_token_is_refused() -> None:
    token = mint_render_token(
        render_id="r1", artifact_id="a1", branch="main", deadline=datetime.now(tz=UTC) - timedelta(seconds=1)
    )

    with pytest.raises(AuthorizationError, match=r"^Expired render token$"):
        validate_render_token(token)


def test_access_token_is_refused() -> None:
    token = generate_access_token(account_id="acc", session_id=uuid.uuid4())

    with pytest.raises(AuthorizationError, match=r"^Invalid token, current token is not a render token$"):
        validate_render_token(token)


@dataclass(frozen=True, kw_only=True)
class MissingClaimCase:
    name: str
    claim: str
    message: str


MISSING_CLAIM_CASES = [
    MissingClaimCase(name="render_id", claim="render_id", message=r"^Invalid render token, a claim is missing$"),
    MissingClaimCase(name="artifact_id", claim="artifact_id", message=r"^Invalid render token, a claim is missing$"),
    MissingClaimCase(name="branch", claim="branch", message=r"^Invalid render token, a claim is missing$"),
    MissingClaimCase(name="exp", claim="exp", message=r"^Invalid render token$"),
]


@pytest.mark.parametrize("case", MISSING_CLAIM_CASES, ids=lambda case: case.name)
def test_missing_claim_is_refused(case: MissingClaimCase) -> None:
    claims = {"type": "render", "render_id": "r1", "artifact_id": "a1", "branch": "main", "exp": _future()}
    del claims[case.claim]
    token = jwt.encode(claims, SECRET, algorithm="HS256")

    with pytest.raises(AuthorizationError, match=case.message):
        validate_render_token(token)


async def test_access_token_validation_refuses_render_token() -> None:
    token = mint_render_token(render_id="r1", artifact_id="a1", branch="main", deadline=_future())

    with pytest.raises(AuthorizationError, match=r"^Invalid token$"):
        await validate_jwt_access_token(token)

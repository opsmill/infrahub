from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response

from infrahub.api import router as top_level_router
from infrahub.api.ldap import LDAPCredentials, login_ldap

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def _decode(response: JSONResponse) -> dict:
    body = response.body
    assert isinstance(body, (bytes, bytearray, memoryview))
    return json.loads(bytes(body).decode())


@pytest.fixture
def fastapi_response() -> Response:
    return Response()


@pytest.fixture
def credentials() -> LDAPCredentials:
    return LDAPCredentials(username="alice", password="any-non-empty-string")


class _UnusableDB:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(
            f"Community LDAP stub touched the database (attribute {name!r}); "
            "it must raise EnterpriseRequiredError before any DB access."
        )


_NO_DB = cast("InfrahubDatabase", _UnusableDB())


class TestRouterMounting:
    def test_route_is_mounted_under_api_prefix(self) -> None:
        full_paths = {route.path for route in top_level_router.routes if isinstance(route, APIRoute)}
        assert "/api/auth/ldap/login" in full_paths


class TestLDAPCredentialsValidation:
    def test_password_excluded_from_repr(self) -> None:
        creds = LDAPCredentials(username="alice", password="sensitive-secret")
        assert "sensitive-secret" not in repr(creds)


class TestCommunityRouteAlwaysReturnsEnterpriseRequired:
    """The community-edition LDAP route is a 403 stub."""

    async def test_returns_403_enterprise_required(
        self, credentials: LDAPCredentials, fastapi_response: Response
    ) -> None:
        result = await login_ldap(credentials=credentials, response=fastapi_response, db=_NO_DB)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 403

    async def test_response_body_matches_documented_envelope(
        self, credentials: LDAPCredentials, fastapi_response: Response
    ) -> None:
        result = await login_ldap(credentials=credentials, response=fastapi_response, db=_NO_DB)
        assert isinstance(result, JSONResponse)
        body = _decode(result)

        assert body["error_code"] == "ENTERPRISE_REQUIRED"
        assert body["feature"] == "ldap_auth"

        if "message" in body and body["message"] is not None:
            assert "ldap_auth" not in body["message"]

    async def test_no_cookies_set_on_failure(self, credentials: LDAPCredentials, fastapi_response: Response) -> None:
        await login_ldap(credentials=credentials, response=fastapi_response, db=_NO_DB)
        assert "set-cookie" not in {h.lower() for h in fastapi_response.headers}

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response

from infrahub.api import router as top_level_router
from infrahub.api.dependencies import get_db
from infrahub.api.exception_handlers import generic_api_exception_handler
from infrahub.api.ldap import LDAPCredentials, login_ldap
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import EnterpriseRequiredError, Error


class UnusableDatabase(InfrahubDatabase):
    """Placeholder injected where a real database would go.

    The community LDAP stub must raise EnterpriseRequiredError before any DB access,
    so this instance is never touched. Skipping the base __init__ leaves the object
    without a driver - any accidental DB call fails loudly with AttributeError.
    """

    def __init__(self) -> None:
        pass


@pytest.fixture
def fastapi_response() -> Response:
    return Response()


@pytest.fixture
def credentials() -> LDAPCredentials:
    return LDAPCredentials(username="alice", password="any-non-empty-string")


async def test_community_login_handler_raises_enterprise_required(
    credentials: LDAPCredentials, fastapi_response: Response
) -> None:
    """The community LDAP service stub raises EnterpriseRequiredError before any DB access.

    The route no longer catches exceptions; FastAPI's exception middleware dispatches them.
    Mapping to the HTTP envelope is the framework's job, not the route's.
    """
    with pytest.raises(EnterpriseRequiredError) as exc_info:
        await login_ldap(credentials=credentials, response=fastapi_response, db=UnusableDatabase())
    assert exc_info.value.feature == "ldap_auth"


@pytest.fixture
def community_ldap_client() -> TestClient:
    app = FastAPI()
    app.include_router(top_level_router)
    app.add_exception_handler(Error, generic_api_exception_handler)
    app.dependency_overrides[get_db] = UnusableDatabase
    return TestClient(app)


def test_community_login_endpoint_returns_403_with_error_envelope(community_ldap_client: TestClient) -> None:
    """POST /api/auth/ldap/login on community returns HTTP 403 with the Infrahub error envelope.

    Exercises FastAPI's exception middleware end-to-end: the community LDAP stub raises
    EnterpriseRequiredError, and the registered handler must convert it to a response
    callers (frontend, scripts) can consume.
    """
    response = community_ldap_client.post(
        "/api/auth/ldap/login",
        json={"username": "alice", "password": "any-non-empty-string"},
    )
    assert response.status_code == 403
    assert response.json() == {
        "data": None,
        "errors": [
            {
                "message": "This feature requires the Infrahub Enterprise edition.",
                "extensions": {"code": 403},
            }
        ],
    }

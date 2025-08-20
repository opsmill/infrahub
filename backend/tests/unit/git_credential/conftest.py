import pytest
from pytest_httpx import HTTPXMock

from infrahub.core.constants import InfrahubKind


@pytest.fixture
async def mock_repositories_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            InfrahubKind.GENERICREPOSITORY: {
                "count": 1,
                "edges": [
                    {
                        "node": {
                            "__typename": InfrahubKind.REPOSITORY,
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                            "credential": {
                                "node": {
                                    "id": "9486cfce-87db-479d-ad73-07d80ba555555",
                                    "__typename": InfrahubKind.PASSWORDCREDENTIAL,
                                    "display_label": "cred01",
                                }
                            },
                        }
                    }
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST", json=response1, match_headers={"X-Infrahub-Tracker": "query-coregenericrepository-page1"}
    )
    return httpx_mock


@pytest.fixture
async def mock_credential_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            InfrahubKind.PASSWORDCREDENTIAL: {
                "edges": [
                    {
                        "node": {
                            "__typename": InfrahubKind.PASSWORDCREDENTIAL,
                            "id": "9486cfce-87db-479d-ad73-07d80ba555555",
                            "name": {"value": "cred01"},
                            "username": {"value": "myusername"},
                            "password": {"value": "mypassword"},
                        }
                    }
                ],
            }
        }
    }

    httpx_mock.add_response(
        method="POST", json=response1, match_headers={"X-Infrahub-Tracker": "query-corepasswordcredential-page1"}
    )
    return httpx_mock

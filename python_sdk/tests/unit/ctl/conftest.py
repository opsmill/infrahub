import pytest
from pytest_httpx import HTTPXMock


@pytest.fixture
async def mock_branches_list_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "Branch": [
                {
                    "id": "eca306cf-662e-4e03-8180-2b788b191d3c",
                    "name": "main",
                    "is_data_only": False,
                    "is_default": True,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                    "is_isolated": False,
                    "has_schema_changes": False,
                },
                {
                    "id": "7d9f817a-b958-4e76-8528-8afd0c689ada",
                    "name": "cr1234",
                    "is_data_only": True,
                    "is_default": False,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                    "is_isolated": True,
                    "has_schema_changes": True,
                },
            ]
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-branch-all"},
    )
    return httpx_mock


@pytest.fixture
async def authentication_error_payload():
    response = {
        "data": None,
        "errors": [
            {
                "message": "Authentication is required to perform this operation",
                "extensions": {"code": 401},
            }
        ],
    }

    return response


@pytest.fixture
async def mock_branch_create_error(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {"BranchCreate": None},
        "errors": [
            {
                "message": 'invalid field name: string does not match regex "^[a-z][a-z0-9\\-]+$"',
                "locations": [{"line": 2, "column": 3}],
                "path": ["BranchCreate"],
            }
        ],
    }

    httpx_mock.add_response(
        status_code=200,
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "mutation-branch-create"},
    )
    return httpx_mock


@pytest.fixture
async def mock_repositories_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            "repository": [
                {
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                    "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                }
            ]
        }
    }
    response2 = {
        "data": {
            "repository": [
                {
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                }
            ]
        }
    }

    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=response1)
    httpx_mock.add_response(method="POST", url="http://mock/graphql/cr1234", json=response2)
    return httpx_mock

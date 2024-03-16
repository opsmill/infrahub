import pytest
from pytest_httpx import HTTPXMock

from infrahub_sdk import InfrahubClient


@pytest.fixture
async def client() -> InfrahubClient:
    return await InfrahubClient.init(address="http://mock", insert_tracker=True)


@pytest.fixture
async def mock_gql_query_my_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"mock": []}}

    httpx_mock.add_response(
        method="POST",
        json=response,
        url="http://localhost:8000/api/query/my_query?branch=main&update_group=false",
    )
    return httpx_mock

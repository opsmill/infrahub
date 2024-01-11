import re

import pytest
from pytest_httpx import HTTPXMock

from infrahub.core.constants import InfrahubKind


@pytest.fixture
async def mock_repositories_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            InfrahubKind.REPOSITORYGENERIC: {
                "count": 1,
                "edges": [
                    {
                        "node": {
                            "__typename": InfrahubKind.REPOSITORY,
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-demo-edge"},
                            "location": {"value": "git@github.com:dgarros/infrahub-demo-edge.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                            "username": {"value": "myusername"},
                            "password": {"value": "mypassword"},
                        }
                    }
                ],
            }
        }
    }

    # Not sure why but when running within infrahub-git-helper the Client is not inserting the tracker
    # So instead of using the tracker we are using a regex in the URL
    httpx_mock.add_response(method="POST", url=re.compile(r"http(.*){3}mock\/graphql\/.*"), json=response1)
    return httpx_mock

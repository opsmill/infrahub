import os

import pytest

from infrahub import config
from infrahub.api import internal
from tests.helpers.fixtures import get_fixtures_dir


@pytest.fixture
def override_search_index_path():
    old_search_index_path = config.SETTINGS.main.docs_index_path
    config.SETTINGS.main.docs_index_path = os.path.join(get_fixtures_dir(), "docs/search-index.json")
    internal.search_docs_loader = internal.SearchDocs()
    yield
    config.SETTINGS.main.docs_index_path = old_search_index_path


@pytest.fixture
def no_search_index_path():
    old_search_index_path = config.SETTINGS.main.docs_index_path
    config.SETTINGS.main.docs_index_path = os.path.join(get_fixtures_dir(), "docs/no-index.json")
    internal.search_docs_loader = internal.SearchDocs()
    yield
    config.SETTINGS.main.docs_index_path = old_search_index_path


async def test_search_docs(client, override_search_index_path):
    response = client.get("/api/search/docs?query=guid")

    assert response.status_code == 200
    assert response.json() is not None
    response_json = response.json()
    assert isinstance(response_json, list)
    assert response_json[0]["title"] == "Guides"


async def test_no_search_docs(client, no_search_index_path):
    response = client.get("/api/search/docs?query=guid")

    assert response.status_code == 404
    assert response.json() is not None
    response_json = response.json()
    assert response_json == {
        "data": None,
        "errors": [{"message": "documentation index not found", "extensions": {"code": 404}}],
    }

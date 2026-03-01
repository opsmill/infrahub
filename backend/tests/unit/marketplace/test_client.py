from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.exceptions import HTTPServerError
from infrahub.marketplace.client import MarketplaceClient


def _make_response(data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    return response


@pytest.fixture()
def mock_http() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def client(mock_http: AsyncMock) -> MarketplaceClient:
    return MarketplaceClient(http=mock_http, base_url="https://marketplace.test")


class TestGetSchemas:
    async def test_returns_parsed_schemas(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.return_value = _make_response(
            {
                "data": {
                    "schemas": {
                        "totalCount": 1,
                        "edges": [
                            {
                                "node": {
                                    "id": "s1",
                                    "name": "device",
                                    "namespace": "infrahub",
                                    "displayName": "Device",
                                    "description": "A device schema",
                                    "downloadCount": 10,
                                    "upvoteCount": 3,
                                    "forkCount": 1,
                                    "visibility": "public",
                                    "tags": [{"id": "t1", "name": "networking"}],
                                    "versions": [
                                        {"id": "v1", "semver": "1.0.0", "status": "published", "downloadCount": 5}
                                    ],
                                }
                            }
                        ],
                    }
                }
            }
        )
        result = await client.get_schemas()
        assert result.total_count == 1
        assert len(result.schemas) == 1
        assert result.schemas[0].display_name == "Device"
        assert result.schemas[0].download_count == 10

        mock_http.post.assert_called_once()
        call_kwargs = mock_http.post.call_args
        assert "marketplace.test/graphql" in call_kwargs.kwargs["url"]

    async def test_handles_graphql_errors(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.return_value = _make_response(
            {"errors": [{"message": "Query failed"}]}
        )
        with pytest.raises(HTTPServerError) as exc_info:
            await client.get_schemas()
        assert "Marketplace GraphQL error" in exc_info.value.message


class TestGetCollections:
    async def test_returns_parsed_collections(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.return_value = _make_response(
            {
                "data": {
                    "collections": {
                        "totalCount": 1,
                        "edges": [
                            {
                                "node": {
                                    "id": "c1",
                                    "name": "base",
                                    "displayName": "Base",
                                    "description": "Base collection",
                                    "schemaCount": 2,
                                    "downloadCount": 5,
                                    "upvoteCount": 1,
                                    "items": [{"id": "s1", "name": "device", "displayName": "Device"}],
                                }
                            }
                        ],
                    }
                }
            }
        )
        result = await client.get_collections()
        assert result.total_count == 1
        assert len(result.collections) == 1
        assert result.collections[0].name == "base"


class TestGetTags:
    async def test_returns_tag_counts(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.return_value = _make_response(
            {
                "data": {
                    "tagCounts": [
                        {"tag": {"id": "t1", "name": "networking"}, "count": 10},
                        {"tag": {"id": "t2", "name": "experimental"}, "count": 5},
                    ]
                }
            }
        )
        result = await client.get_tags()
        assert len(result) == 2
        assert result[0].name == "networking"
        assert result[0].count == 10


class TestGetSchemaVersionContent:
    async def test_returns_version_content(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.return_value = _make_response(
            {
                "data": {
                    "schemaVersion": {
                        "id": "v1",
                        "semver": "1.0.0",
                        "content": "---\nnodes: []",
                        "downloadUrl": "https://marketplace.test/dl/v1",
                        "dependencies": [{"id": "d1", "name": "base", "namespace": "infrahub"}],
                    }
                }
            }
        )
        result = await client.get_schema_version_content(version_id="v1")
        assert result.semver == "1.0.0"
        assert result.content == "---\nnodes: []"
        assert len(result.dependencies) == 1

    async def test_not_found_raises(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.return_value = _make_response({"data": {"schemaVersion": None}})
        with pytest.raises(HTTPServerError) as exc_info:
            await client.get_schema_version_content(version_id="nonexistent")
        assert "not found" in exc_info.value.message

    async def test_http_error_propagates(self, client: MarketplaceClient, mock_http: AsyncMock):
        mock_http.post.side_effect = HTTPServerError(message="Connection refused")
        with pytest.raises(HTTPServerError) as exc_info:
            await client.get_schema_version_content(version_id="v1")
        assert "Connection refused" in exc_info.value.message

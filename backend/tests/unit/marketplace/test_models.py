import pytest
from pydantic import ValidationError

from infrahub.marketplace.models import (
    MarketplaceCollectionResponse,
    MarketplaceInstallRequest,
    MarketplaceSchemaResponse,
    MarketplaceVersionContent,
    MarketplaceVersionSummary,
)


class TestMarketplaceSchemaResponse:
    def test_parse_camel_case_aliases(self):
        data = {
            "id": "abc-123",
            "name": "test-schema",
            "namespace": "infrahub",
            "displayName": "Test Schema",
            "description": "A test schema",
            "downloadCount": 42,
            "upvoteCount": 5,
            "forkCount": 2,
            "visibility": "public",
            "tags": [{"id": "t1", "name": "networking"}],
            "versions": [{"id": "v1", "semver": "1.0.0", "status": "published", "downloadCount": 10}],
        }
        schema = MarketplaceSchemaResponse.model_validate(data)
        assert schema.display_name == "Test Schema"
        assert schema.download_count == 42
        assert schema.upvote_count == 5
        assert schema.fork_count == 2
        assert len(schema.tags) == 1
        assert schema.tags[0].name == "networking"
        assert len(schema.versions) == 1
        assert schema.versions[0].semver == "1.0.0"
        assert schema.versions[0].download_count == 10

    def test_defaults_for_optional_counts(self):
        data = {
            "id": "abc-123",
            "name": "test-schema",
            "namespace": "infrahub",
            "displayName": "Test",
            "description": "desc",
        }
        schema = MarketplaceSchemaResponse.model_validate(data)
        assert schema.download_count == 0
        assert schema.upvote_count == 0
        assert schema.fork_count == 0
        assert schema.tags == []
        assert schema.versions == []

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            MarketplaceSchemaResponse.model_validate({"id": "abc-123", "name": "test"})


class TestMarketplaceVersionContent:
    def test_parse_version_content(self):
        data = {
            "id": "v1",
            "semver": "1.0.0",
            "content": "---\nversion: '1.0'\nnodes: []",
            "downloadUrl": "https://marketplace.infrahub.app/download/v1",
            "dependencies": [{"id": "d1", "name": "base", "namespace": "infrahub"}],
        }
        version = MarketplaceVersionContent.model_validate(data)
        assert version.download_url == "https://marketplace.infrahub.app/download/v1"
        assert len(version.dependencies) == 1
        assert version.dependencies[0].name == "base"

    def test_empty_dependencies(self):
        data = {
            "id": "v1",
            "semver": "1.0.0",
            "content": "schema content",
            "downloadUrl": "https://example.com/dl",
        }
        version = MarketplaceVersionContent.model_validate(data)
        assert version.dependencies == []


class TestMarketplaceCollectionResponse:
    def test_parse_collection(self):
        data = {
            "id": "col-1",
            "name": "base",
            "displayName": "Base Schema",
            "description": "Base schemas collection",
            "schemaCount": 3,
            "downloadCount": 10,
            "upvoteCount": 2,
            "items": [{"id": "s1", "name": "device", "displayName": "Device"}],
        }
        collection = MarketplaceCollectionResponse.model_validate(data)
        assert collection.display_name == "Base Schema"
        assert collection.schema_count == 3
        assert len(collection.items) == 1
        assert collection.items[0].display_name == "Device"

    def test_nullable_display_name(self):
        data = {
            "id": "col-1",
            "name": "base",
            "description": "desc",
        }
        collection = MarketplaceCollectionResponse.model_validate(data)
        assert collection.display_name is None


class TestMarketplaceVersionSummary:
    def test_parse_version_summary(self):
        data = {"id": "v1", "semver": "2.0.0", "status": "published", "downloadCount": 99}
        version = MarketplaceVersionSummary.model_validate(data)
        assert version.download_count == 99


class TestMarketplaceInstallRequest:
    def test_valid_install_request(self):
        req = MarketplaceInstallRequest(
            repository_id="repo-1",
            schema_version_ids=["v1", "v2"],
            branch_name="main",
        )
        assert req.repository_id == "repo-1"
        assert len(req.schema_version_ids) == 2

    def test_empty_version_ids_raises(self):
        with pytest.raises(ValidationError):
            MarketplaceInstallRequest(
                repository_id="repo-1",
                schema_version_ids=[],
                branch_name="main",
            )

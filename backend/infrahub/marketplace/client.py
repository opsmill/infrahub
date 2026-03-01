from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.exceptions import HTTPServerError
from infrahub.log import get_logger
from infrahub.marketplace.models import (
    MarketplaceCollectionResponse,
    MarketplaceCollectionsListResponse,
    MarketplaceSchemaResponse,
    MarketplaceSchemasListResponse,
    MarketplaceTagCount,
    MarketplaceVersionContent,
)

if TYPE_CHECKING:
    from infrahub.services.adapters.http import InfrahubHTTP

log = get_logger()

SCHEMAS_QUERY = """
query MarketplaceSchemas {
  schemas {
    totalCount
    edges {
      node {
        id
        name
        namespace
        displayName
        description
        downloadCount
        upvoteCount
        forkCount
        visibility
        tags { id, name }
        versions { id, semver, status, downloadCount }
      }
    }
  }
}
"""

COLLECTIONS_QUERY = """
query MarketplaceCollections {
  collections {
    totalCount
    edges {
      node {
        id
        name
        namespace
        displayName
        description
        schemaCount
        downloadCount
        upvoteCount
        items {
          id
          position
          schema { id, name, namespace, displayName, description }
        }
      }
    }
  }
}
"""

TAGS_QUERY = """
query MarketplaceTags {
  tagCounts { tag { id, name }, count }
}
"""

SCHEMA_VERSION_CONTENT_QUERY = """
query SchemaVersionContent($id: ID!) {
  schemaVersion(id: $id) {
    id
    semver
    content
    downloadUrl
    dependencies {
      referencedKind
      isResolved
      resolvedSchema { id, name, namespace }
    }
  }
}
"""

SCHEMA_BY_ID_QUERY = """
query SchemaById($id: ID!) {
  schemaById(id: $id) {
    id
    name
    namespace
    latestVersion {
      id
      semver
      content
      downloadUrl
      dependencies {
        referencedKind
        isResolved
        resolvedSchema { id, name, namespace }
      }
    }
  }
}
"""


class MarketplaceClient:
    """Client for querying the Infrahub Marketplace GraphQL API."""

    def __init__(self, http: InfrahubHTTP, base_url: str = "https://marketplace.infrahub.app") -> None:
        self.http = http
        self.graphql_url = f"{base_url}/graphql"

    async def _execute_query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query against the marketplace API."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await self.http.post(
                url=self.graphql_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=True,
            )
        except HTTPServerError:
            log.warning("marketplace_unreachable", url=self.graphql_url)
            raise

        data = response.json()
        if "errors" in data:
            error_messages = "; ".join(e.get("message", "Unknown error") for e in data["errors"])
            raise HTTPServerError(message=f"Marketplace GraphQL error: {error_messages}")

        return data.get("data", {})

    async def get_schemas(self) -> MarketplaceSchemasListResponse:
        """Fetch all available schemas from the marketplace."""
        data = await self._execute_query(query=SCHEMAS_QUERY)
        schemas_data = data.get("schemas", {})
        edges = schemas_data.get("edges", [])
        schemas = [MarketplaceSchemaResponse.model_validate(edge["node"]) for edge in edges]
        return MarketplaceSchemasListResponse(
            schemas=schemas,
            total_count=schemas_data.get("totalCount", len(schemas)),
        )

    async def get_collections(self) -> MarketplaceCollectionsListResponse:
        """Fetch all available collections from the marketplace."""
        data = await self._execute_query(query=COLLECTIONS_QUERY)
        collections_data = data.get("collections", {})
        edges = collections_data.get("edges", [])
        collections = [MarketplaceCollectionResponse.model_validate(edge["node"]) for edge in edges]
        return MarketplaceCollectionsListResponse(
            collections=collections,
            total_count=collections_data.get("totalCount", len(collections)),
        )

    async def get_tags(self) -> list[MarketplaceTagCount]:
        """Fetch available tags with counts from the marketplace."""
        data = await self._execute_query(query=TAGS_QUERY)
        tag_counts = data.get("tagCounts", [])
        return [
            MarketplaceTagCount(
                id=tc["tag"]["id"],
                name=tc["tag"]["name"],
                count=tc.get("count", 0),
            )
            for tc in tag_counts
        ]

    async def get_schema_version_content(self, *, version_id: str) -> MarketplaceVersionContent:
        """Fetch the full content of a specific schema version.

        The version_id may be an actual version ID or a schema ID.
        Tries schemaVersion first, then falls back to schemaById with latestVersion.
        """
        # Try as a version ID first
        data = await self._execute_query(
            query=SCHEMA_VERSION_CONTENT_QUERY,
            variables={"id": version_id},
        )
        version_data = data.get("schemaVersion")
        if version_data:
            return MarketplaceVersionContent.model_validate(version_data)

        # Fall back to schema ID → latestVersion
        data = await self._execute_query(
            query=SCHEMA_BY_ID_QUERY,
            variables={"id": version_id},
        )
        schema_data = data.get("schemaById")
        if schema_data and schema_data.get("latestVersion"):
            return MarketplaceVersionContent.model_validate(schema_data["latestVersion"])

        raise HTTPServerError(message=f"Schema or version {version_id} not found in the marketplace")

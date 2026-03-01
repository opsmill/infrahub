from __future__ import annotations

from pydantic import BaseModel, Field


class MarketplaceTag(BaseModel, frozen=True):
    id: str
    name: str


class MarketplaceVersionSummary(BaseModel, frozen=True):
    id: str
    semver: str
    status: str
    download_count: int = Field(alias="downloadCount", default=0)


class MarketplaceSchemaResponse(BaseModel, frozen=True):
    id: str
    name: str
    namespace: str
    display_name: str = Field(alias="displayName")
    description: str
    download_count: int = Field(alias="downloadCount", default=0)
    upvote_count: int = Field(alias="upvoteCount", default=0)
    fork_count: int = Field(alias="forkCount", default=0)
    visibility: str = "public"
    tags: list[MarketplaceTag] = Field(default_factory=list)
    versions: list[MarketplaceVersionSummary] = Field(default_factory=list)


class MarketplaceDependencySchema(BaseModel, frozen=True):
    id: str
    name: str
    namespace: str


class MarketplaceDependency(BaseModel, frozen=True):
    referenced_kind: str = Field(alias="referencedKind")
    is_resolved: bool = Field(alias="isResolved")
    resolved_schema: MarketplaceDependencySchema | None = Field(alias="resolvedSchema", default=None)


class MarketplaceVersionContent(BaseModel, frozen=True):
    id: str
    semver: str
    content: str
    download_url: str = Field(alias="downloadUrl")
    dependencies: list[MarketplaceDependency] = Field(default_factory=list)


class MarketplaceCollectionItemSchema(BaseModel, frozen=True):
    id: str
    name: str
    namespace: str
    display_name: str | None = Field(alias="displayName", default=None)
    description: str = ""


class MarketplaceCollectionItem(BaseModel, frozen=True):
    id: str
    position: int = 0
    schema_info: MarketplaceCollectionItemSchema = Field(alias="schema")


class MarketplaceCollectionResponse(BaseModel, frozen=True):
    id: str
    name: str
    namespace: str
    display_name: str | None = Field(alias="displayName", default=None)
    description: str
    schema_count: int = Field(alias="schemaCount", default=0)
    download_count: int = Field(alias="downloadCount", default=0)
    upvote_count: int = Field(alias="upvoteCount", default=0)
    items: list[MarketplaceCollectionItem] = Field(default_factory=list)


class MarketplaceTagCount(BaseModel, frozen=True):
    id: str
    name: str
    count: int = 0


class MarketplaceSchemasListResponse(BaseModel, frozen=True):
    schemas: list[MarketplaceSchemaResponse] = Field(default_factory=list)
    total_count: int = 0


class MarketplaceCollectionsListResponse(BaseModel, frozen=True):
    collections: list[MarketplaceCollectionResponse] = Field(default_factory=list)
    total_count: int = 0


class MarketplaceInstallRequest(BaseModel):
    repository_id: str
    schema_ids: list[str] = Field(default_factory=list, description="Schema refs as namespace/name")
    collection_ids: list[str] = Field(default_factory=list, description="Collection refs as namespace/name")
    branch_name: str


class MarketplaceInstallModel(BaseModel, frozen=True):
    repository_id: str
    schema_ids: list[str] = Field(default_factory=list)
    collection_ids: list[str] = Field(default_factory=list)
    branch_name: str
    marketplace_url: str = "https://marketplace.infrahub.app"

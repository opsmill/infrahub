from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MarketplaceItemKind = Literal["schema", "collection"]

_SEMVER_RE = r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"


class MarketplaceTag(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str


class MarketplaceTagCount(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    count: int


class MarketplaceAuthor(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    username: str
    avatar_url: str | None = None


class MarketplaceVersionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    semver: str
    status: Literal["published", "draft", "deprecated"] = "published"
    changelog: str | None = None
    download_count: int = 0
    download_url: str
    created_at: datetime


class MarketplaceSchemaSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    namespace: str
    name: str
    display_name: str | None = None
    description: str | None = None
    visibility: Literal["public", "private"] = "public"
    download_count: int = 0
    upvote_count: int = 0
    fork_count: int = 0
    viewer_has_upvoted: bool = False
    created_at: datetime
    updated_at: datetime
    author: MarketplaceAuthor
    tags: list[MarketplaceTag] = Field(default_factory=list)
    latest_version: MarketplaceVersionSummary | None = None
    already_installed: bool = False


class MarketplaceSchemaDetail(MarketplaceSchemaSummary):
    versions: list[MarketplaceVersionSummary] = Field(default_factory=list)
    readme: str | None = None


class MarketplaceVersionContent(BaseModel):
    model_config = ConfigDict(frozen=True)
    version_id: str
    semver: str
    content: str
    content_type: Literal["schema"] = "schema"
    sha256: str | None = None


class MarketplaceCollectionItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    namespace: str
    name: str
    semver: str
    order: int = 0


class MarketplaceCollectionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    namespace: str
    name: str
    display_name: str | None = None
    description: str | None = None
    schema_count: int = 0
    download_count: int = 0
    author: MarketplaceAuthor
    tags: list[MarketplaceTag] = Field(default_factory=list)
    already_installed: bool = False


class MarketplaceCollectionDetail(MarketplaceCollectionSummary):
    items: list[MarketplaceCollectionItem] = Field(default_factory=list)
    readme: str | None = None


class PageInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    has_next_page: bool = False
    end_cursor: str | None = None


class MarketplaceSchemasListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[MarketplaceSchemaSummary] = Field(default_factory=list)
    page_info: PageInfo = Field(default_factory=PageInfo)
    total_count: int = 0


class MarketplaceCollectionsListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[MarketplaceCollectionSummary] = Field(default_factory=list)
    page_info: PageInfo = Field(default_factory=PageInfo)
    total_count: int = 0


class MarketplaceTagsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    tags: list[MarketplaceTagCount] = Field(default_factory=list)


class MarketplaceStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    marketplace_url: str
    url_configured: bool
    url_scheme_valid: bool
    upstream_reachable: bool
    checked_at: datetime


class MarketplaceInstallItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: MarketplaceItemKind
    namespace: str
    name: str
    semver: str | None = None

    @field_validator("semver")
    @classmethod
    def _validate_semver(cls, value: str | None) -> str | None:
        if value is None:
            return value
        import re

        if not re.match(_SEMVER_RE, value):
            raise ValueError(f"Invalid semver: {value!r}")
        return value


class MarketplaceInstallRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    repository_id: str
    branch_name: str
    items: list[MarketplaceInstallItem]

    @field_validator("items")
    @classmethod
    def _validate_items(cls, value: list[MarketplaceInstallItem]) -> list[MarketplaceInstallItem]:
        if not value:
            raise ValueError("items must not be empty")
        if len(value) > 50:
            raise ValueError("items must not exceed 50 entries")
        return value


class MarketplaceInstallResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: str
    message: str


class MarketplaceInstallPayload(BaseModel):
    """Prefect flow parameter payload for `marketplace-schema-install`."""

    model_config = ConfigDict(frozen=True)
    marketplace_url: str
    initiator_username: str
    initiator_user_id: str
    repository_id: str
    branch_name: str
    items: list[MarketplaceInstallItem]


class CliSnippetDownload(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: MarketplaceItemKind
    namespace: str
    name: str
    semver: str | None = None
    command: str


class CliSnippetResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    downloads: list[CliSnippetDownload]
    load_command: str
    rendered: str

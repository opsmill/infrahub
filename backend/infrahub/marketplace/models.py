from __future__ import annotations

import re
from datetime import datetime  # noqa: TC003  -- Pydantic needs this available at runtime for field validation
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self

MarketplaceItemKind = Literal["schema", "collection"]

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
# Conservative branch-name charset: matches git's ref-name rules closely enough
# to avoid anything that could be parsed as a git CLI flag (leading '-'), a
# path-traversal token ('..'), or a control/whitespace char. We're stricter
# than git here because this value is user-controlled and we never need the
# full ref-name grammar.
_BRANCH_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/\-]*$")


class MarketplaceTag(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str | None = None
    name: str


class MarketplaceTagCount(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str | None = None
    name: str
    count: int = 0


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
    model_config = ConfigDict(frozen=True, populate_by_name=True)
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
    updated_at: datetime | None = None
    author: MarketplaceAuthor | None = Field(default=None, validation_alias=AliasChoices("author", "created_by"))
    tags: list[MarketplaceTag] = Field(default_factory=list)
    latest_version: MarketplaceVersionSummary | None = None


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
    model_config = ConfigDict(frozen=True, populate_by_name=True)
    id: str
    namespace: str
    name: str
    display_name: str | None = None
    description: str | None = None
    schema_count: int = 0
    download_count: int = 0
    author: MarketplaceAuthor | None = Field(default=None, validation_alias=AliasChoices("author", "created_by"))


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
        if not _SEMVER_RE.match(value):
            raise ValueError(f"Invalid semver: {value!r}")
        return value


MarketplaceInstallTarget = Literal["repository", "direct"]


def _validate_branch_name(value: str) -> str:
    """Reject branch names that could be parsed as git CLI flags or path traversal."""
    if not value or ".." in value or not _BRANCH_NAME_RE.match(value):
        raise ValueError(
            f"Invalid branch_name: {value!r} (must match {_BRANCH_NAME_RE.pattern}, no '..' sequences, no leading '-')"
        )
    return value


class MarketplaceInstallRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    target: MarketplaceInstallTarget = "repository"
    repository_id: str | None = None
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

    @field_validator("branch_name")
    @classmethod
    def _branch_name_must_be_safe(cls, value: str) -> str:
        return _validate_branch_name(value)

    @field_validator("repository_id")
    @classmethod
    def _normalize_repository_id(cls, value: str | None) -> str | None:
        """Collapse the empty/whitespace string to None so downstream checks
        only need to test for None, not for both None and ""."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _require_repo_id_for_repo_target(self) -> Self:
        """target="repository" requires a repository_id; target="direct" ignores it.

        Raising here yields a Pydantic 422 with field-level detail, which is
        fine for schema-driven clients. The router additionally raises a plain
        400 for the same case because its callers expect install-level error
        codes rather than validation-envelope shapes.
        """
        if self.target == "repository" and not self.repository_id:
            raise ValueError("repository_id is required when target is 'repository'")
        return self


class MarketplaceInstallResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: str
    message: str


class MarketplaceInstallPayload(BaseModel):
    """Prefect flow parameter payload for `marketplace-schema-install`.

    ``initiator_account_id`` is the Infrahub account UUID; ``initiator_username``
    is the resolved display name. Both are used to construct the git commit
    ``Actor`` so the commit author reflects who ran the install, not the
    worker's default identity.
    """

    model_config = ConfigDict(frozen=True)
    marketplace_url: str
    initiator_account_id: str
    initiator_username: str
    repository_id: str
    branch_name: str
    items: list[MarketplaceInstallItem]


class MarketplaceInstallDirectPayload(BaseModel):
    """Prefect flow parameter payload for `marketplace-schema-install-direct`.

    Direct installs apply schemas to the running Infrahub instance via the
    schema-load API — no Git commit, no repository required.
    """

    model_config = ConfigDict(frozen=True)
    marketplace_url: str
    initiator_account_id: str
    initiator_username: str
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

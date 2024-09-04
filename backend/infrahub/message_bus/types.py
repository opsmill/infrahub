from __future__ import annotations

import re
from enum import Enum

from infrahub_sdk.client import NodeDiff  # noqa: TCH002
from pydantic import BaseModel, Field

from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.exceptions import NodeNotFoundError

SCHEMA_CHANGE = re.compile("^Schema[A-Z]")


class MessageTTL(int, Enum):
    """Defines the message TTL in seconds, the values themselves are in milliseconds."""

    FIVE = 5000
    TEN = 10000
    TWENTY = 20000

    @classmethod
    def variations(cls) -> list[MessageTTL]:
        """Return available variations of message time to live."""
        return [cls(cls.__members__[member].value) for member in list(cls.__members__)]


class KVTTL(int, Enum):
    """Defines the KV TTL in seconds."""

    ONE = 1
    TEN = 10
    FIFTEEN = 15
    TWO_HOURS = 7200

    @classmethod
    def variations(cls) -> list[KVTTL]:
        """Return available variations of KV time to live."""
        return [cls(cls.__members__[member].value) for member in list(cls.__members__)]


class ProposedChangeRepository(BaseModel):
    repository_id: str
    repository_name: str
    read_only: bool
    source_branch: str
    destination_branch: str
    internal_status: str
    source_commit: str = Field(default="")
    destination_commit: str = Field(default="")
    conflicts: list[str] = Field(default_factory=list, description="List of files with merge conflicts")
    files_added: list[str] = Field(default_factory=list)
    files_changed: list[str] = Field(default_factory=list)
    files_removed: list[str] = Field(default_factory=list)

    @property
    def has_diff(self) -> bool:
        """Indicates if a diff exists for managed repositories."""
        if not self.read_only and self.source_commit and self.source_commit != self.destination_commit:
            return True
        return False

    @property
    def is_staging(self) -> bool:
        """Indicates if the repository is in staging mode."""
        if self.internal_status == RepositoryInternalStatus.STAGING.value:
            return True
        return False

    @property
    def kind(self) -> str:
        if self.read_only:
            return InfrahubKind.READONLYREPOSITORY
        return InfrahubKind.REPOSITORY

    @property
    def has_modifications(self) -> bool:
        """Indicates if any of the files in the repository has been modified."""
        return bool(self.files_added + self.files_changed + self.files_removed)


class ProposedChangeSubscriber(BaseModel):
    subscriber_id: str
    kind: str


class ProposedChangeArtifactDefinition(BaseModel):
    definition_id: str
    definition_name: str
    query_name: str
    query_models: list[str]
    repository_id: str
    transform_kind: str
    template_path: str = Field(default="")
    class_name: str = Field(default="")
    content_type: str
    file_path: str = Field(default="")
    timeout: int

    @property
    def transform_location(self) -> str:
        if self.transform_kind == InfrahubKind.TRANSFORMJINJA2:
            return self.template_path
        if self.transform_kind == InfrahubKind.TRANSFORMPYTHON:
            return f"{self.file_path}::{self.class_name}"

        raise ValueError("Invalid kind for Transform")


class ProposedChangeGeneratorDefinition(BaseModel):
    definition_id: str
    definition_name: str
    query_name: str
    convert_query_response: bool
    query_models: list[str]
    repository_id: str
    class_name: str
    file_path: str
    parameters: dict
    group_id: str


class ProposedChangeBranchDiff(BaseModel):
    diff_summary: list[NodeDiff] = Field(default_factory=list, description="The DiffSummary between two branches")
    repositories: list[ProposedChangeRepository] = Field(default_factory=list)
    subscribers: list[ProposedChangeSubscriber] = Field(default_factory=list)

    def get_repository(self, repository_id: str) -> ProposedChangeRepository:
        for repository in self.repositories:
            if repository_id == repository.repository_id:
                return repository
        raise NodeNotFoundError(node_type="Repository", identifier=repository_id)

    def get_subscribers_ids(self, kind: str) -> list[str]:
        return [subscriber.subscriber_id for subscriber in self.subscribers if subscriber.kind == kind]

    def has_node_changes(self, branch: str) -> bool:
        """Indicates if there is at least one node object that has been modified in the branch"""
        return bool(
            [
                entry
                for entry in self.diff_summary
                if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
            ]
        )

    def has_data_changes(self, branch: str) -> bool:
        """Indicates if there are node or schema changes within the branch."""
        return bool([entry for entry in self.diff_summary if entry["branch"] == branch])

    @property
    def has_file_modifications(self) -> bool:
        """Indicates modifications to any of the files in the Git repositories."""
        return any(repository.has_modifications for repository in self.repositories)

    def modified_nodes(self, branch: str) -> list[str]:
        """Return a list of non schema nodes that have been modified on the branch"""
        return [
            entry["id"]
            for entry in self.diff_summary
            if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
        ]

    def modified_kinds(self, branch: str) -> list[str]:
        """Return a list of non schema kinds that have been modified on the branch"""
        return list(
            {
                entry["kind"]
                for entry in self.diff_summary
                if entry["branch"] == branch and not SCHEMA_CHANGE.match(entry["kind"])
            }
        )

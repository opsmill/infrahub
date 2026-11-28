from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

from fast_depends import Depends, inject

from infrahub.git.repository import get_initialized_repo

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.protocols import CoreArtifact

    from infrahub.artifacts.models import CheckArtifactCreate
    from infrahub.git.integrator import ArtifactGenerateResult


class ArtifactRenderer(Protocol):
    async def render_artifact(
        self, artifact: CoreArtifact, artifact_created: bool, message: CheckArtifactCreate
    ) -> ArtifactGenerateResult: ...


class ArtifactRepositories(ABC):
    """Open the repository that renders the artifact of an artifact check."""

    @abstractmethod
    async def open(self, client: InfrahubClient, model: CheckArtifactCreate) -> ArtifactRenderer:
        raise NotImplementedError


class GitArtifactRepositories(ArtifactRepositories):
    async def open(self, client: InfrahubClient, model: CheckArtifactCreate) -> ArtifactRenderer:
        return await get_initialized_repo(
            client=client,
            repository_id=model.repository_id,
            name=model.repository_name,
            repository_kind=model.repository_kind,
            infrahub_branch_name=model.branch_name,
            commit=model.commit,
        )


def build_artifact_repositories() -> ArtifactRepositories:
    return GitArtifactRepositories()


@inject
def get_artifact_repositories(
    repositories: ArtifactRepositories = Depends(build_artifact_repositories),  # noqa: B008
) -> ArtifactRepositories:
    return repositories

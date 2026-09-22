from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.protocols import CoreRepository

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.exceptions import RepositoryError


@dataclass(frozen=True)
class RepositoryGraphSettings:
    """The configuration a read-write repository object takes from its node in the graph."""

    default_branch: str
    internal_status: RepositoryInternalStatus
    location: str


class RepositoryNodeReader(Protocol):
    """The one graph read a read-write repository construction needs."""

    async def get(
        self,
        kind: type[CoreRepository],
        raise_when_missing: Literal[True],
        branch: str | None = ...,
        id: str | None = ...,
        exclude: list[str] | None = ...,
        **kwargs: Any,
    ) -> CoreRepository: ...


async def resolve_graph_settings(
    *, client: RepositoryNodeReader, repository_id: str, repository_name: str, infrahub_branch_name: str
) -> RepositoryGraphSettings:
    """Read a read-write repository's configuration from its node on a given Infrahub branch.

    The branch is significant: ``internal_status`` is branch-scoped, and a repository created inside
    a branch exists only on that branch until its proposed change merges.

    Raises:
        RepositoryError: When the node cannot be read, whatever the underlying reason. The SDK's own
            errors do not derive from it, while the callers that isolate a single repository's
            failure catch only ``RepositoryError`` and ``CommitNotFoundError`` - so an unwrapped one
            would abort a whole synchronization cycle instead of skipping one repository.

    """
    try:
        repository = await client.get(
            kind=CoreRepository,
            id=repository_id,
            branch=infrahub_branch_name,
            exclude=["tags", "credential"],
            raise_when_missing=True,
        )
    except SdkError as exc:
        raise RepositoryError(
            identifier=repository_name,
            message=(
                f"Unable to read the configuration of repository {repository_name} "
                f"on branch {infrahub_branch_name}: {exc}"
            ),
        ) from exc

    return RepositoryGraphSettings(
        default_branch=repository.default_branch.value,
        internal_status=RepositoryInternalStatus(repository.internal_status.value),
        location=repository.location.value,
    )

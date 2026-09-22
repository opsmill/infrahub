from dataclasses import dataclass
from typing import Any, Literal

import pytest
from infrahub_sdk.exceptions import BranchNotFoundError, NodeNotFoundError
from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.protocols import CoreRepository
from infrahub_sdk.protocols_base import Dropdown, String

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.exceptions import RepositoryError
from infrahub.git.graph_settings import resolve_graph_settings


class StubString(String):
    def __init__(self, value: str) -> None:
        self.value = value


class StubDropdown(Dropdown):
    def __init__(self, value: str) -> None:
        self.value = value


class StubRepositoryNode(CoreRepository):
    """A repository node exposing only the attributes the resolver reads."""

    def __init__(self, *, default_branch: str, internal_status: str, location: str) -> None:
        self.default_branch = StubString(default_branch)
        self.internal_status = StubDropdown(internal_status)
        self.location = StubString(location)


class RecordingReader:
    """Answers every read with one node and records the id and branch each read targeted."""

    def __init__(self, node: CoreRepository) -> None:
        self._node = node
        self.reads: list[tuple[str | None, str | None]] = []

    async def get(
        self,
        kind: type[CoreRepository],
        raise_when_missing: Literal[True],
        branch: str | None = None,
        id: str | None = None,
        exclude: list[str] | None = None,
        **kwargs: Any,
    ) -> CoreRepository:
        self.reads.append((id, branch))
        return self._node


class FailingReader:
    """Raises one SDK error instead of answering, to pin how the resolver wraps it."""

    def __init__(self, error: SdkError) -> None:
        self._error = error

    async def get(
        self,
        kind: type[CoreRepository],
        raise_when_missing: Literal[True],
        branch: str | None = None,
        id: str | None = None,
        exclude: list[str] | None = None,
        **kwargs: Any,
    ) -> CoreRepository:
        raise self._error


async def test_resolve_graph_settings_returns_the_node_values() -> None:
    reader = RecordingReader(
        StubRepositoryNode(default_branch="develop", internal_status="staging", location="/remotes/repo1")
    )

    settings = await resolve_graph_settings(
        client=reader, repository_id="repo-id-1", repository_name="repo1", infrahub_branch_name="production"
    )

    assert settings.default_branch == "develop"
    assert settings.internal_status == RepositoryInternalStatus.STAGING
    assert settings.location == "/remotes/repo1"


async def test_resolve_graph_settings_reads_the_node_on_the_branch_it_was_given() -> None:
    """The branch is what makes a repository that exists only inside a branch resolvable."""
    reader = RecordingReader(
        StubRepositoryNode(default_branch="main", internal_status="active", location="/remotes/repo1")
    )

    await resolve_graph_settings(
        client=reader, repository_id="repo-id-1", repository_name="repo1", infrahub_branch_name="staging-branch"
    )

    assert reader.reads == [("repo-id-1", "staging-branch")]


@dataclass
class SdkErrorCase:
    name: str
    error: SdkError


@pytest.mark.parametrize(
    "case",
    [
        SdkErrorCase(name="missing_node", error=NodeNotFoundError(identifier={"id": ["repo-id-1"]})),
        SdkErrorCase(name="missing_branch", error=BranchNotFoundError(identifier="production")),
    ],
    ids=lambda case: case.name,
)
async def test_resolve_graph_settings_wraps_sdk_errors(case: SdkErrorCase) -> None:
    """Callers isolating one repository's failure catch RepositoryError only."""
    reader = FailingReader(case.error)

    with pytest.raises(
        RepositoryError, match=r"^Unable to read the configuration of repository repo1 on branch production: "
    ) as raised:
        await resolve_graph_settings(
            client=reader, repository_id="repo-id-1", repository_name="repo1", infrahub_branch_name="production"
        )

    assert raised.value.identifier == "repo1"
    assert raised.value.__cause__ is case.error

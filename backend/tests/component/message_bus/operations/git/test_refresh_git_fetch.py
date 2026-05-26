import re
from pathlib import Path

import pytest
from fast_depends import Provider
from git import Repo
from pytest_httpx import HTTPXMock

from infrahub.core.constants import InfrahubKind
from infrahub.git import InfrahubRepository
from infrahub.message_bus import messages
from infrahub.message_bus.operations.git.repository import fetch
from infrahub.workers.dependencies import build_client


@pytest.mark.httpx_mock(should_mock=lambda request: request.url.host == "mock")
async def test_fan_out_pins_to_orchestrator_commit_when_upstream_advances(
    git_fixture_repo: InfrahubRepository,
    git_sources_dir: Path,
    dependency_provider: Provider,
    httpx_mock: HTTPXMock,
) -> None:
    """Fan-out workers must land on the SHA pinned by the sync orchestrator.

    When upstream advances between the orchestrator pinning a SHA and a worker
    processing the fan-out, the worker must check out the pinned SHA rather
    than fast-forwarding to whatever upstream HEAD currently is.
    """
    httpx_mock.add_response(
        method="POST",
        url=re.compile(r"http://mock/graphql/.*"),
        json={"data": {"CoreGenericRepositoryUpdate": {"ok": True}}},
        is_reusable=True,
        is_optional=True,
    )

    branch_name = "main"
    branch_id = "8808dcea-f7b4-4f5a-b5e9-a0605d4c11ba"

    upstream = Repo(str(git_sources_dir / "test_base"))
    pinned_sha = str(upstream.head.commit)

    new_file = git_sources_dir / "test_base" / "late_commit.txt"
    new_file.write_text("upstream advanced after fan-out started", encoding="utf-8")
    upstream.index.add(["late_commit.txt"])
    upstream.index.commit("Upstream commit landed after fan-out started")
    later_sha = str(upstream.head.commit)
    assert pinned_sha != later_sha

    message = messages.RefreshGitFetch(
        location=str(git_sources_dir / "test_base"),
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        infrahub_branch_name=branch_name,
        infrahub_branch_id=branch_id,
        commit=pinned_sha,
    )

    with dependency_provider.scope(build_client, lambda: git_fixture_repo.sdk):
        await fetch.fn(message=message)

    worktree = git_fixture_repo.get_git_repo_worktree(identifier=branch_name)
    assert str(worktree.head.commit) == pinned_sha

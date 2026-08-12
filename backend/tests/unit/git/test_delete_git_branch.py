from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.git import InfrahubRepository


async def test_has_branch_returns_true_for_existing_branch(git_repo_01: InfrahubRepository) -> None:
    assert git_repo_01.origin_has_branch("branch01") is True


async def test_has_branch_returns_false_for_missing_branch(git_repo_01: InfrahubRepository) -> None:
    assert git_repo_01.origin_has_branch("nonexistent-branch-xyz") is False


async def test_delete_remote_branch_removes_branch_from_origin(
    git_repo_01: InfrahubRepository,
    git_upstream_repo_01: dict[str, str | Path],
) -> None:
    assert git_repo_01.origin_has_branch("clean-branch") is True

    await git_repo_01.delete_remote_branch(branch_name="clean-branch")

    # Fetch to sync remote tracking refs, then verify it's gone
    await git_repo_01.fetch()
    assert git_repo_01.origin_has_branch("clean-branch") is False

    # Verify branch is also gone from the upstream (origin) repo
    upstream = Repo(git_upstream_repo_01["path"])
    upstream_branches = [b.name for b in upstream.refs if not b.is_remote()]
    assert "clean-branch" not in upstream_branches


@pytest.mark.parametrize("branch_name", ["branch01", "branch02"])
async def test_has_branch_true_for_all_remote_branches(git_repo_01: InfrahubRepository, branch_name: str) -> None:
    assert git_repo_01.origin_has_branch(branch_name) is True

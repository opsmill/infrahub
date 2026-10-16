"""Repository-setup scenarios for InfrahubRepository against a real Gogs server.

These tests exercise the clone-and-initialize path under two conditions only a
real server can expose faithfully: a clone URL whose host is reachable but
whose repository path does not exist (the server responds with a 404), and a
clone against a freshly-created repository with no commits and no branches.

The two scenarios pin two distinct contracts. A reachable host with no
repository at the given path must produce a typed connection/not-found error
so operators can distinguish a missing-repository condition from authentication
failures, network outages, or invalid URL formatting. A clone of an empty
repository must fail loudly — the checkout step cannot land on a default
branch that does not exist — rather than leaving the worker holding an empty
worktree it cannot meaningfully use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import httpx
import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import GOGS_ADMIN, GOGS_PASSWORD

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


def _create_empty_gogs_repo(base_url: str, token: str, repo_name: str) -> str:
    """Create an empty Gogs repository (no auto-init, no commits) and return the clone URL.

    Differs from the standard helper, which initializes the repo with a
    `.infrahub.yml` and a `main` branch. Here we want the post-creation state
    a fresh `git init --bare` would produce on the server: no refs, no objects.
    """
    resp = httpx.post(
        f"{base_url}/api/v1/user/repos",
        headers={"Authorization": f"token {token}"},
        json={"name": repo_name, "auto_init": False, "private": False},
        timeout=5.0,
    )
    assert resp.status_code in (200, 201), f"Empty repo creation failed ({resp.status_code}): {resp.text}"

    parsed = urlparse(base_url)
    netloc_with_auth = f"{GOGS_ADMIN}:{GOGS_PASSWORD}@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{GOGS_ADMIN}/{repo_name}.git"


def _nonexistent_repo_url(base_url: str, repo_name: str) -> str:
    """Build a clone URL pointing at a reachable host but a path that does not exist."""
    parsed = urlparse(base_url)
    netloc_with_auth = f"{GOGS_ADMIN}:{GOGS_PASSWORD}@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{GOGS_ADMIN}/{repo_name}.git"


class TestRepositorySetup(TestInfrahubApp):
    """Repository-setup paths against a real Gogs server."""

    @pytest.fixture(scope="class")
    async def missing_repo_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "setup-missing-on-server-repo"
        bad_url = _nonexistent_repo_url(gogs_server.base_url, repo_name)

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=bad_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "bad_url": bad_url}

    @pytest.fixture(scope="class")
    async def empty_repo_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "setup-empty-repo"
        clone_url = _create_empty_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name)

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=clone_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "clone_url": clone_url}

    async def test_new_against_reachable_url_without_repository_raises_typed_error(
        self,
        missing_repo_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Cloning a non-existent repository on a reachable host raises a typed repository error.

        The host responds, accepts the credentials, then returns a 404 for the
        requested repository path. Without a typed error at this boundary,
        callers would have to grep the underlying Git stderr to tell apart a
        missing repository from an auth failure or a DNS error — three
        conditions whose remediation steps are completely different.
        """
        repo_name = missing_repo_dataset["repo_name"]
        bad_url = missing_repo_dataset["bad_url"]

        with pytest.raises(RepositoryError):
            await InfrahubRepository.new(
                id=missing_repo_dataset["node_id"],
                name=repo_name,
                location=bad_url,
                client=client,
            )

    async def test_new_against_empty_repository_fails_at_default_branch_checkout(
        self,
        empty_repo_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Cloning an empty repository raises a typed repository error at default-branch checkout.

        An empty repository has no refs and no objects. The clone succeeds —
        Git is happy to clone a refless remote — but the subsequent checkout
        of the default branch has nothing to land on. The failure must surface
        as a typed error rather than leaving the worktree in an indeterminate
        state, so the operational status of the repository node reflects the
        problem and operators can fix it (push a first commit, change the
        configured default branch) rather than silently accepting an unusable
        local clone.
        """
        repo_name = empty_repo_dataset["repo_name"]
        clone_url = empty_repo_dataset["clone_url"]

        with pytest.raises(RepositoryError):
            await InfrahubRepository.new(
                id=empty_repo_dataset["node_id"],
                name=repo_name,
                location=clone_url,
                client=client,
            )

"""Authentication and access scenarios for InfrahubRepository against a real Gogs server.

These tests exercise paths where the remote rejects an operation for auth or
permission reasons. They guard the contract that callers can react to credential
failures and access denials without parsing raw `git` output: a credential failure
must surface as a typed `RepositoryCredentialsError`, and an access-denied push
must propagate the remote's response in a form the caller can inspect.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import httpx
import pytest
from git.exc import GitCommandError

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryCredentialsError
from infrahub.git.repository import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import bad_credentials_clone_url, create_gogs_repo

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


READONLY_USER = "readonlyuser"
READONLY_PASSWORD = "readonly1234"
READONLY_EMAIL = "readonly@test.local"


def _create_readonly_user(base_url: str, admin_token: str) -> None:
    """Create a non-admin Gogs user. Idempotent within a session."""
    resp = httpx.post(
        f"{base_url}/api/v1/admin/users",
        headers={"Authorization": f"token {admin_token}"},
        json={
            "username": READONLY_USER,
            "email": READONLY_EMAIL,
            "password": READONLY_PASSWORD,
            "send_notify": False,
        },
        timeout=5.0,
    )
    # 201 on creation, 422 if the user already exists from a previous test in the session.
    if resp.status_code not in (201, 422):
        pytest.fail(f"Failed to create readonly user ({resp.status_code}): {resp.text}")


def _add_read_collaborator(base_url: str, admin_token: str, owner: str, repo: str, collaborator: str) -> None:
    """Add `collaborator` to `owner/repo` with read-only permission."""
    resp = httpx.put(
        f"{base_url}/api/v1/repos/{owner}/{repo}/collaborators/{collaborator}",
        headers={"Authorization": f"token {admin_token}"},
        json={"permission": "read"},
        timeout=5.0,
    )
    if resp.status_code not in (200, 204):
        pytest.fail(
            f"Failed to add {collaborator} as read collaborator on {owner}/{repo} ({resp.status_code}): {resp.text}"
        )


def _readonly_user_clone_url(base_url: str, repo_owner: str, repo_name: str) -> str:
    """HTTP clone URL embedding the read-only user's credentials."""
    parsed = urlparse(base_url)
    netloc_with_auth = f"{READONLY_USER}:{READONLY_PASSWORD}@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{repo_owner}/{repo_name}.git"


class TestAuthAndAccess(TestInfrahubApp):
    """Authentication and access against a real Gogs server."""

    @pytest.fixture(scope="class")
    async def bad_credentials_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "auth-bad-credentials-repo"
        # Private repo: anonymous read is denied, so bad credentials are always presented.
        create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
            private=True,
        )
        bad_url = bad_credentials_clone_url(gogs_server.base_url, repo_name)

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=bad_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "bad_url": bad_url}

    @pytest.fixture(scope="class")
    async def no_write_access_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        gogs_server: GogsServer,
    ) -> dict:
        repo_name = "auth-no-write-access-repo"
        # Private repo owned by admin. Adding readonlyuser as a Read collaborator lets
        # them clone successfully but denies push at the server.
        create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
            private=True,
        )
        _create_readonly_user(gogs_server.base_url, gogs_server.token)
        _add_read_collaborator(gogs_server.base_url, gogs_server.token, gogs_server.admin, repo_name, READONLY_USER)
        readonly_url = _readonly_user_clone_url(gogs_server.base_url, gogs_server.admin, repo_name)

        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(db=db, name=repo_name, location=readonly_url)
        await obj.save(db=db)
        return {"repo_name": repo_name, "node_id": obj.id, "readonly_url": readonly_url}

    async def test_clone_with_wrong_credentials_preserves_remote_message_in_cause(
        self,
        bad_credentials_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Clone with invalid credentials raises RepositoryCredentialsError.

        The typed exception's own message is a static placeholder from the exception
        class. The remote's response text reaches the caller through the chained
        `GitCommandError`'s stderr — without the typed exception, callers cannot
        distinguish auth failures from other git errors, and without the chain,
        the remote's diagnostic text is lost.
        """
        with pytest.raises(RepositoryCredentialsError, match=r"Authentication failed for"):
            await InfrahubRepository.new(
                id=bad_credentials_dataset["node_id"],
                name=bad_credentials_dataset["repo_name"],
                location=bad_credentials_dataset["bad_url"],
                client=client,
            )

    async def test_push_without_write_access_raises_bare_git_command_error(
        self,
        no_write_access_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Push as a read-only user surfaces a bare GitCommandError carrying the 403.

        `InfrahubRepository.push` does not catch exceptions from
        `GitPython.Remote.push`. When the server returns HTTP 403 on a
        no-write-access push, GitPython raises a raw `GitCommandError` that
        propagates unchanged to the caller; the remote's response is reachable
        only via `error.stderr`. This test pins that shape so that any change
        to `push`'s error-handling path explicitly updates the expected
        exception type and message contract.
        """
        repo_name = no_write_access_dataset["repo_name"]
        readonly_url = no_write_access_dataset["readonly_url"]

        # Successful clone — read-only access is sufficient.
        infrahub_repo = await InfrahubRepository.new(
            id=no_write_access_dataset["node_id"],
            name=repo_name,
            location=readonly_url,
            client=client,
        )

        # Make a local commit on main so there is something to push.
        git_repo = infrahub_repo.get_git_repo_main()
        local_file = Path(str(git_repo.working_dir)) / "no_write_access_commit.txt"
        local_file.write_text("local-only content")
        git_repo.index.add(["no_write_access_commit.txt"])
        git_repo.index.commit("Commit that should be rejected by remote permission")

        # GitPython raises GitCommandError on HTTP 403; push() does not catch it.
        with pytest.raises(GitCommandError, match=r"403"):
            await infrahub_repo.push("main")

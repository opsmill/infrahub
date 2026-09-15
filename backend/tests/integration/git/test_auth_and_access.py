"""Authentication and access scenarios for InfrahubRepository against a real Gogs server.

These tests exercise paths where the remote rejects an operation for auth or
permission reasons. They guard the contract that callers can react to credential
failures and access denials without parsing raw `git` output: a credential failure
must surface as a typed `RepositoryCredentialsError`, and a push denied for lack of
write access must surface as a typed `RepositoryPermissionError`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.exceptions import RepositoryCredentialsError, RepositoryPermissionError
from infrahub.git.repository import InfrahubRepository
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import (
    bad_credentials_clone_url,
    create_gogs_repo,
    grant_read_access,
    readonly_clone_url,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer


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
        # Private repo owned by admin. Granting the read-only user Read access lets them
        # clone successfully but denies push at the server.
        create_gogs_repo(
            gogs_server.base_url,
            gogs_server.token,
            repo_name,
            gogs_server.container,
            private=True,
        )
        grant_read_access(gogs_server.base_url, gogs_server.token, repo_name)
        readonly_url = readonly_clone_url(gogs_server.base_url, repo_name)

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

    async def test_push_without_write_access_raises_permission_error(
        self,
        no_write_access_dataset: dict,
        client: InfrahubClient,
    ) -> None:
        """Pushing as a read-only user raises a typed RepositoryPermissionError whose cause carries the 403.

        A read-only credential clones successfully but is denied at push time; the caller gets a typed
        permission error rather than raw git output, and the remote's HTTP 403 response is still
        reachable on the exception's chained cause.
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

        with pytest.raises(
            RepositoryPermissionError,
            match=rf"^Access to repository {repo_name} was denied; the credentials are not authorized for the operation\.$",
        ) as exc_info:
            await infrahub_repo.push("main")

        # The remote's response is preserved on the chained cause, not swallowed by the typed error.
        assert "403" in str(exc_info.value.__cause__)

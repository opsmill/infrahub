from __future__ import annotations

import base64
import os
import shlex
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import httpx
import pytest
from testcontainers.core.container import DockerContainer

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from tests.helpers.git import GogsServer

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreRepository
    from infrahub.database import InfrahubDatabase

GOGS_ADMIN = "gogsadmin"
GOGS_PASSWORD = "admin1234"
GOGS_EMAIL = "admin@test.local"
GOGS_READONLY = "gogsreader"
GOGS_READONLY_PASSWORD = "reader1234"
GOGS_READONLY_EMAIL = "reader@test.local"
# 0.14+ enforces write authorization when advertising git-receive-pack, so a read-only
# collaborator is rejected at connect time; 0.13.0 deferred that check to the actual push.
GOGS_IMAGE = "gogs/gogs:0.14.3"


def _wait_for_http(url: str, timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=1.0, follow_redirects=True)
            if resp.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    pytest.fail(f"HTTP endpoint {url} did not become available within {timeout}s")


def _create_api_token(base_url: str) -> str:
    deadline = time.monotonic() + 30
    last_status: int | None = None
    last_location: str = ""
    while time.monotonic() < deadline:
        try:
            resp = httpx.post(
                f"{base_url}/api/v1/users/{GOGS_ADMIN}/tokens",
                auth=(GOGS_ADMIN, GOGS_PASSWORD),
                json={"name": "infrahub-test-token"},
                timeout=5.0,
            )
            last_status = resp.status_code
            last_location = resp.headers.get("location", "")
            if resp.status_code == 201:
                return resp.json()["sha1"]
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    pytest.fail(f"Failed to create Gogs API token within 30s (last status={last_status}, location={last_location!r})")


def _create_gogs_user(container: DockerContainer, username: str, password: str, email: str, admin: bool) -> None:
    args = ["/app/gogs/gogs", "admin", "create-user", "--name", username, "--password", password, "--email", email]
    if admin:
        args.append("--admin")
    result = container.get_wrapped_container().exec_run(args, user="git", workdir="/app/gogs")
    # exit_code != 0 is acceptable if the user was already created by a previous run.
    if result.exit_code != 0:
        output = result.output.decode()
        assert "already exist" in output or "user already exists" in output, (
            f"create-user failed for {username} (exit {result.exit_code}): {output}"
        )


def gogs_clone_url(base_url: str, repo_name: str) -> str:
    """Return an HTTP clone URL with embedded credentials for the admin user's repo."""
    parsed = urlparse(base_url)
    netloc_with_auth = f"{GOGS_ADMIN}:{GOGS_PASSWORD}@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{GOGS_ADMIN}/{repo_name}.git"


def readonly_clone_url(base_url: str, repo_name: str) -> str:
    """Return a clone URL authenticated as a user with read-only access to the admin's repo.

    This is the shape of a read-write repository whose credentials can read but not push: the
    user authenticates and can clone, but the remote rejects a push.
    """
    parsed = urlparse(base_url)
    netloc_with_auth = f"{GOGS_READONLY}:{GOGS_READONLY_PASSWORD}@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{GOGS_ADMIN}/{repo_name}.git"


def grant_read_access(base_url: str, token: str, repo_name: str) -> None:
    """Add the read-only user as a read collaborator on the admin's repo."""
    resp = httpx.put(
        f"{base_url}/api/v1/repos/{GOGS_ADMIN}/{repo_name}/collaborators/{GOGS_READONLY}",
        headers={"Authorization": f"token {token}"},
        json={"permission": "read"},
        timeout=5.0,
    )
    assert resp.status_code in (200, 204), f"Granting read access failed ({resp.status_code}): {resp.text}"


def create_remote_ref(container: DockerContainer, repo_name: str, ref_name: str, based_on: str = "main") -> None:
    """Create a branch ref directly in the server's bare repository."""
    bare = f"/data/git/repositories/{GOGS_ADMIN}/{repo_name}.git"
    result = container.get_wrapped_container().exec_run(
        ["git", f"--git-dir={bare}", "branch", ref_name, based_on],
        user="git",
    )
    assert result.exit_code == 0, f"Creating ref {ref_name} failed (exit {result.exit_code}): {result.output.decode()}"


def bad_credentials_clone_url(base_url: str, repo_name: str) -> str:
    """Return an HTTP clone URL with a non-existent user and wrong password.

    Using a username that does not exist in the system credential store prevents
    any cached credentials from being substituted, so git always presents the
    embedded (bad) credentials to the server.
    """
    parsed = urlparse(base_url)
    netloc_with_auth = f"baduser:wrongpassword@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{GOGS_ADMIN}/{repo_name}.git"


def create_gogs_repo(
    base_url: str,
    token: str,
    repo_name: str,
    container: DockerContainer,
    private: bool = False,
    create_main: bool = True,
) -> str:
    """Create a Gogs repository and return its clone URL.

    The pinned Gogs image initialises repos with 'master' as the default branch; Infrahub
    expects 'main'. We create the 'main' branch directly in the container's bare repository
    via git exec, which stays independent of the Gogs version's branch-API surface.

    Pass private=True to create a private repository (required when testing auth failures,
    since public repos allow anonymous clone access and never present credentials to the server).

    Pass create_main=False to leave 'master' as the only branch, giving a remote that a
    repository left at Infrahub's default of 'main' cannot use.
    """
    resp = httpx.post(
        f"{base_url}/api/v1/user/repos",
        headers={"Authorization": f"token {token}"},
        json={"name": repo_name, "auto_init": True, "readme": "Default", "private": private},
        timeout=5.0,
    )
    assert resp.status_code in (200, 201), f"Repo creation failed ({resp.status_code}): {resp.text}"

    # Use git exec inside the container to:
    #   1. Add a minimal '.infrahub.yml' (required by Infrahub on sync)
    #   2. Create a 'main' branch (Infrahub's default; Gogs initialises with 'master')
    script = (
        f"set -e && "
        f"rm -rf /tmp/{repo_name} && "
        f"git clone /data/git/repositories/{GOGS_ADMIN}/{repo_name}.git /tmp/{repo_name} && "
        f"cd /tmp/{repo_name} && "
        f"git config user.email 'infrahub@test.local' && "
        f"git config user.name 'Infrahub Test' && "
        f"printf -- '---\\n' > .infrahub.yml && "
        f"git add .infrahub.yml && "
        f"git commit -m 'Add .infrahub.yml' && "
        f"git push origin master"
    )
    if create_main:
        script += " && git checkout -b main && git push origin main"

    result = container.get_wrapped_container().exec_run(
        ["bash", "-c", script],
        user="git",
    )
    assert result.exit_code == 0, (
        f"Repo setup failed for {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )

    return gogs_clone_url(base_url, repo_name)


def _gogs_git(container: DockerContainer, repo_name: str, *args: str, failure: str) -> str:
    """Run git against the server's bare repository, which needs neither a clone nor an identity."""
    result = container.get_wrapped_container().exec_run(
        ["git", f"--git-dir=/data/git/repositories/{GOGS_ADMIN}/{repo_name}.git", *args],
        user="git",
    )
    assert result.exit_code == 0, f"{failure} (exit {result.exit_code}): {result.output.decode()}"
    return result.output.decode().strip()


def gogs_repo_branch_commit(container: DockerContainer, repo_name: str, branch: str) -> str:
    """Return the commit a branch points at in the remote."""
    return _gogs_git(container, repo_name, "rev-parse", branch, failure=f"Unable to read {branch} of {repo_name}")


def gogs_branches_containing(container: DockerContainer, repo_name: str, commit: str) -> list[str]:
    """Return the remote branches whose history contains a commit."""
    output = _gogs_git(
        container,
        repo_name,
        "branch",
        "--format=%(refname:short)",
        "--contains",
        commit,
        failure=f"Unable to list the branches of {repo_name} that contain {commit}",
    )
    return output.splitlines()


def gogs_commit_parents(container: DockerContainer, repo_name: str, commit: str) -> list[str]:
    """Return the parents of a remote commit, the first parent first."""
    output = _gogs_git(
        container,
        repo_name,
        "rev-list",
        "--parents",
        "-n",
        "1",
        commit,
        failure=f"Unable to read {commit} of {repo_name}",
    )
    return output.split()[1:]


def gogs_repo_tag(container: DockerContainer, repo_name: str, tag_name: str, commit_ish: str = "master") -> None:
    """Create a lightweight tag in the remote."""
    _gogs_git(container, repo_name, "tag", tag_name, commit_ish, failure=f"Tagging {repo_name} failed")


def _write_files_script(files: dict[str, str]) -> str:
    """Return shell commands writing each file into the current directory, whatever characters it holds."""
    commands = []
    for path, content in files.items():
        encoded = base64.b64encode(content.encode()).decode()
        commands.append(f"echo {encoded} | base64 -d > {shlex.quote(path)}")
    return " && ".join(commands)


def commit_to_remote_branch(
    container: DockerContainer,
    repo_name: str,
    branch: str,
    files: dict[str, str],
    base: str = "main",
    amend: bool = False,
) -> str:
    """Commit files on a remote branch, creating it from ``base`` when absent, and return the new head.

    Reuses the working clone that create_gogs_repo() left in /tmp/{repo_name}.

    Args:
        amend: Replace the last commit of the branch and force-push it, as a rebase or an amended
            commit does, so the branch no longer holds the commit it pointed at.

    """
    commit = (
        f"git commit --amend -m 'Rewritten commit on {branch}'"
        if amend
        else f"git commit -m 'Remote commit on {branch}'"
    )
    push = f"git push --force origin {branch}" if amend else f"git push origin {branch}"
    script = (
        f"set -e && "
        f"cd /tmp/{repo_name} && "
        f"git fetch origin && "
        f"if git rev-parse --verify --quiet origin/{branch} > /dev/null; "
        f"then git checkout -B {branch} origin/{branch}; else git checkout -B {branch} origin/{base}; fi && "
        f"{_write_files_script(files)} && "
        f"git add -A && "
        f"{commit} && "
        f"{push}"
    )
    result = container.get_wrapped_container().exec_run(["bash", "-c", script], user="git")
    assert result.exit_code == 0, f"Remote commit failed (exit {result.exit_code}): {result.output.decode()}"
    return gogs_repo_branch_commit(container, repo_name, branch)


def tracked_branch_files(repo_name: str, version: int) -> dict[str, str]:
    """Return a repository configuration declaring one query named after its version.

    Query names are unique across repositories, so the name carries the repository's name too.
    """
    query_name = f"{repo_name.replace('-', '_')}_v{version}"
    return {
        ".infrahub.yml": f"---\nqueries:\n  - name: {query_name}\n    file_path: tracked_query.gql\n",
        "tracked_query.gql": f"query {query_name} {{ BuiltinTag {{ edges {{ node {{ name {{ value }} }} }} }} }}\n",
    }


@dataclass(frozen=True)
class TrackedBranchRepository:
    name: str
    node_id: str
    branch_name: str
    trunk_commit: str
    imported_commit: str
    """The head of the tracked branch that Infrahub imported and recorded in the graph."""


@pytest.fixture
def tracked_branch_repository(
    db: InfrahubDatabase, client: InfrahubClient, gogs_server: GogsServer, import_every_remote_branch: None
) -> Callable[[str, str], Awaitable[TrackedBranchRepository]]:
    """Return a factory for a Gogs repository whose non-default branch Infrahub has already imported.

    The branch carries one commit of its own, declaring the first version of a query.
    """

    async def create(repo_name: str, branch_name: str) -> TrackedBranchRepository:
        location = create_gogs_repo(gogs_server.base_url, gogs_server.token, repo_name, gogs_server.container)
        imported_commit = commit_to_remote_branch(
            gogs_server.container, repo_name, branch_name, files=tracked_branch_files(repo_name=repo_name, version=1)
        )
        node = await client.create(kind=InfrahubKind.REPOSITORY, data={"name": repo_name, "location": location})
        await node.save()

        recorded: CoreRepository = await NodeManager.get_one(
            db=db, id=node.id, kind=InfrahubKind.REPOSITORY, branch=branch_name, raise_on_error=True
        )
        assert recorded.commit.value == imported_commit, "the tracked branch was not imported when it was added"

        return TrackedBranchRepository(
            name=repo_name,
            node_id=node.id,
            branch_name=branch_name,
            trunk_commit=gogs_repo_branch_commit(gogs_server.container, repo_name, "main"),
            imported_commit=imported_commit,
        )

    return create


@pytest.fixture(scope="session")
def gogs_server() -> Generator[GogsServer, None, None]:
    """Start a Gogs container, initialize it, and yield connection info."""
    os.environ.setdefault("GIT_TERMINAL_PROMPT", "0")

    container = DockerContainer(GOGS_IMAGE).with_exposed_ports(3000)
    container.start()

    try:
        port = container.get_exposed_port(3000)
        base_url = f"http://localhost:{port}"

        _wait_for_http(f"{base_url}/install")

        resp = httpx.post(
            f"{base_url}/install",
            data={
                "db_type": "SQLite3",
                "db_path": "data/gogs.db",
                "app_name": "Gogs Test",
                "repo_root_path": "/data/git/repositories",
                "run_user": "git",
                "domain": "localhost",
                "ssh_port": "22",
                "http_port": "3000",
                "app_url": f"http://localhost:{port}/",
                "log_root_path": "/app/gogs/log",
            },
            follow_redirects=True,
            timeout=15.0,
        )
        assert resp.status_code == 200, f"Gogs install failed ({resp.status_code}): {resp.text}"

        # After install Gogs rewrites its config and may restart its HTTP listener.
        # Wait for the home page (not /install) to be available before calling the API.
        _wait_for_http(f"{base_url}/", timeout=30)

        # The read-only user is the credential that can read but not push in the write-probe tests.
        _create_gogs_user(container, GOGS_ADMIN, GOGS_PASSWORD, GOGS_EMAIL, admin=True)
        _create_gogs_user(container, GOGS_READONLY, GOGS_READONLY_PASSWORD, GOGS_READONLY_EMAIL, admin=False)

        token = _create_api_token(base_url)

        yield GogsServer(
            base_url=base_url,
            port=port,
            token=token,
            admin=GOGS_ADMIN,
            password=GOGS_PASSWORD,
            container=container,
        )
    finally:
        container.stop()


@pytest.fixture
def delete_branch_after_merge_reset_config() -> Generator[None, None, None]:
    original = config.SETTINGS.main.delete_branch_after_merge
    yield
    config.SETTINGS.main.delete_branch_after_merge = original


@pytest.fixture
def delete_git_branch_after_merge_reset_config() -> Generator[None, None, None]:
    original = config.SETTINGS.git.delete_git_branch_after_merge
    yield
    config.SETTINGS.git.delete_git_branch_after_merge = original


@pytest.fixture
def fast_forward_merges() -> Generator[None, None, None]:
    """Merge without creating an explicit merge commit, so the destination fast-forwards to the source tip.

    A test that must know the resulting commit before the merge runs can only do so when the
    destination fast-forwards: an explicit merge commit is created by the merge itself and its hash
    cannot be derived beforehand.
    """
    original = config.SETTINGS.git.use_explicit_merge_commit
    config.SETTINGS.git.use_explicit_merge_commit = False
    yield
    config.SETTINGS.git.use_explicit_merge_commit = original


@pytest.fixture
def import_every_remote_branch() -> Generator[None, None, None]:
    """Import every remote branch, whatever INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES holds in the ambient environment.

    An empty list disables branch-name filtering. Without this, a value exported in the developer's
    shell leaks into the test process and silently drops the branches the test relies on.
    """
    original = config.SETTINGS.git.import_sync_branch_names
    config.SETTINGS.git.import_sync_branch_names = []
    yield
    config.SETTINGS.git.import_sync_branch_names = original

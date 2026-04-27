from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

import httpx
import pytest
from testcontainers.core.container import DockerContainer

from infrahub import config
from tests.helpers.git import GogsServer

if TYPE_CHECKING:
    from collections.abc import Generator

GOGS_ADMIN = "gogsadmin"
GOGS_PASSWORD = "admin1234"
GOGS_EMAIL = "admin@test.local"
GOGS_IMAGE = "gogs/gogs:0.13.0"


def _wait_for_http(url: str, timeout: int = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=1.0, follow_redirects=True)
            if resp.status_code < 500:
                return
        except Exception:  # noqa: S110
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
        except Exception:  # noqa: S110
            pass
        time.sleep(0.5)
    pytest.fail(f"Failed to create Gogs API token within 30s (last status={last_status}, location={last_location!r})")


def gogs_clone_url(base_url: str, repo_name: str) -> str:
    """Return an HTTP clone URL with embedded credentials for the admin user's repo."""
    parsed = urlparse(base_url)
    netloc_with_auth = f"{GOGS_ADMIN}:{GOGS_PASSWORD}@{parsed.netloc}"
    auth_base = urlunparse(parsed._replace(netloc=netloc_with_auth))
    return f"{auth_base}/{GOGS_ADMIN}/{repo_name}.git"


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
    base_url: str, token: str, repo_name: str, container: DockerContainer, private: bool = False
) -> str:
    """Create a Gogs repository and return its clone URL.

    Gogs 0.13.0 initialises repos with 'master' as the default branch; Infrahub
    expects 'main'.  The branch-create API endpoint was added after 0.13.0, so we
    create the 'main' branch directly in the container's bare repository via git exec.

    Pass private=True to create a private repository (required when testing auth failures,
    since public repos allow anonymous clone access and never present credentials to the server).
    """
    resp = httpx.post(
        f"{base_url}/api/v1/user/repos",
        headers={"Authorization": f"token {token}"},
        json={"name": repo_name, "auto_init": True, "readme": "Default", "private": private},
        timeout=5.0,
    )
    assert resp.status_code in (200, 201), f"Repo creation failed ({resp.status_code}): {resp.text}"

    # Gogs 0.13.0 lacks the Contents and branch-create API endpoints.
    # Use git exec inside the container to:
    #   1. Add a minimal '.infrahub.yml' (required by Infrahub on sync)
    #   2. Create a 'main' branch (Infrahub's default; Gogs 0.13.0 uses 'master')
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
        f"git push origin master && "
        f"git checkout -b main && "
        f"git push origin main"
    )
    result = container.get_wrapped_container().exec_run(
        ["bash", "-c", script],
        user="git",
    )
    assert result.exit_code == 0, (
        f"Repo setup failed for {repo_name} (exit {result.exit_code}): {result.output.decode()}"
    )

    return gogs_clone_url(base_url, repo_name)


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

        # Create the admin user via the Gogs CLI — more reliable than the install form's
        # optional admin section, which is silently skipped on some Gogs versions.
        result = container.get_wrapped_container().exec_run(
            [
                "/app/gogs/gogs",
                "admin",
                "create-user",
                "--name",
                GOGS_ADMIN,
                "--password",
                GOGS_PASSWORD,
                "--email",
                GOGS_EMAIL,
                "--admin",
            ],
            user="git",
            workdir="/app/gogs",
        )
        # exit_code != 0 is acceptable if the user was already created by the install form.
        if result.exit_code != 0:
            output = result.output.decode()
            assert "already exist" in output or "user already exists" in output, (
                f"create-user failed (exit {result.exit_code}): {output}"
            )

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

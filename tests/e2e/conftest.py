"""Pytest fixtures for the Infrahub pytest-playwright e2e suite.

This replaces the legacy CI bring-up (`invoke dev.start dev.load-infra-schema
dev.load-infra-data dev.infra-git-import dev.infra-git-create`) with:

* a single session-scoped Infrahub stack started via infrahub-testcontainers, and
* composable, per-domain data fixtures that load the EXACT same dataset
  (the base schema, the navigation menu, the `infrastructure_edge.py` demo data
  and the `demo-edge` Git repository) so each test declares precisely what it
  needs.

Bring-up modes
--------------
* Default (CI / local): no ``INFRAHUB_ADDRESS`` in the environment -> a fresh
  Infrahub stack is booted with infrahub-testcontainers and the data fixtures
  provision it.
* Pre-provisioned: set ``INFRAHUB_ADDRESS`` to point at an already-running,
  already-loaded Infrahub (e.g. one started with ``invoke dev.start
  dev.load-infra-*``). The container is not booted and the data fixtures become
  no-ops, so the same specs run unchanged against either backend.

The suite is intentionally located outside ``backend/tests/`` so it does not
inherit ``backend/tests/conftest.py`` (which spins up an in-process backend).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml
from infrahub_sdk import Config, InfrahubClientSync
from infrahub_testcontainers import __version__ as infrahub_testcontainers_version
from infrahub_testcontainers.container import PROJECT_ENV_VARIABLES, InfrahubDockerCompose
from playwright.sync_api import expect

# Make `constants`/`helpers` importable from test modules in any subdirectory.
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    ADMIN_API_TOKEN,
    ADMIN_CREDENTIALS,
    BASE_SCHEMA_FILES,
    READ_ONLY_CREDENTIALS,
    READ_WRITE_CREDENTIALS,
)
from helpers import BranchAPI, login

if TYPE_CHECKING:
    from collections.abc import Generator

    from playwright.sync_api import Browser, Page

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models"
DEMO_EDGE_REPO_FIXTURE = REPO_ROOT / "backend/tests/fixtures/repos/infrahub-demo-edge/initial__main"

# How long the demo-data generator (models/infrastructure_edge.py) may run.
INFRASTRUCTURE_DATA_TIMEOUT = 30 * 60

# pytest-playwright defaults the `expect` assertion timeout to 5s. The legacy TS
# suite ran with a 60s (local) / 180s (CI) expect timeout, so async UI updates
# (toasts, table refreshes, branch/task settling) had ample time. Match that
# spirit with a generous default; individual assertions can still override.
expect.set_options(timeout=30_000)


# --------------------------------------------------------------------------- #
# Infrahub stack (infrahub-testcontainers)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def infrahub_provisioned_externally() -> bool:
    """Whether INFRAHUB_ADDRESS points at an already-provisioned Infrahub.

    In that mode we neither boot a container nor (re)load data.
    """
    return bool(os.environ.get("INFRAHUB_ADDRESS"))


@pytest.fixture(scope="session")
def infrahub_version() -> str:
    """Image version to run.

    Returns "local" (resolved to INFRAHUB_TESTING_IMAGE_VER by
    InfrahubDockerCompose.init) when a locally built image is provided, else the
    installed infrahub-testcontainers version.
    """
    return "local" if os.environ.get("INFRAHUB_TESTING_IMAGE_VER") else infrahub_testcontainers_version


@pytest.fixture(scope="session")
def infrahub_compose_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Per-session compose context directory.

    The `repos` and `backups` directories must exist before docker compose
    starts because they are bind-mounted into the containers (the remote Git
    directory is mounted at /remote).
    """
    directory = tmp_path_factory.mktemp("infrahub-e2e")
    (directory / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]).mkdir(exist_ok=True)
    (directory / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_DB_BACKUP_DIRECTORY"]).mkdir(exist_ok=True)
    return directory


@pytest.fixture(scope="session")
def infrahub_app(
    request: pytest.FixtureRequest,
    infrahub_compose_dir: Path,
    infrahub_version: str,
) -> Generator[dict[str, int], None, None]:
    """Boot one Infrahub stack for the whole session and expose service ports.

    Mirrors infrahub_testcontainers.helpers.TestInfrahubDocker.infrahub_app but
    at session scope so the entire e2e suite shares a single instance (as the
    legacy TS suite did).
    """
    compose = InfrahubDockerCompose.init(directory=infrahub_compose_dir, version=infrahub_version)
    try:
        compose.start()
    except Exception as exc:  # pragma: no cover - surfaced with logs for debugging
        stdout, stderr = compose.get_logs()
        raise RuntimeError(f"Failed to start docker compose:\nStdout:\n{stdout}\nStderr:\n{stderr}") from exc

    yield compose.get_services_port()

    if request.session.testsfailed:
        stdout, stderr = compose.get_logs("infrahub-server", "task-worker")
        warnings.warn(f"Container logs:\nStdout:\n{stdout}\nStderr:\n{stderr}", stacklevel=2)
    compose.stop()


@pytest.fixture(scope="session")
def infrahub_address(request: pytest.FixtureRequest, infrahub_provisioned_externally: bool) -> str:
    """Base URL of the Infrahub server under test.

    Prefers an externally supplied INFRAHUB_ADDRESS; otherwise lazily boots the
    testcontainers stack (via the `infrahub_app` fixture) and derives the mapped
    host port of the load-balanced server.
    """
    if infrahub_provisioned_externally:
        return os.environ["INFRAHUB_ADDRESS"].rstrip("/")
    port = request.getfixturevalue("infrahub_app")["server"]
    return f"http://localhost:{port}"


@pytest.fixture(scope="session")
def infrahub_client(infrahub_address: str) -> InfrahubClientSync:
    """Admin SDK (sync) client.

    Sync on purpose, to coexist cleanly with the synchronous pytest-playwright
    `page` fixture (no event-loop juggling).
    """
    return InfrahubClientSync(config=Config(address=infrahub_address, api_token=ADMIN_API_TOKEN))


# --------------------------------------------------------------------------- #
# Composable data fixtures (faithful reproduction of the demo dataset)
# --------------------------------------------------------------------------- #
def _run_infrahubctl(args: list[str], address: str, *, cwd: Path = REPO_ROOT, timeout: int = 600) -> str:
    """Run an ``infrahubctl`` command against ``address`` with the admin token.

    Used for operations without a first-class sync SDK entry point (loading the
    menu and running the demo-data generator script), exactly as the legacy
    ``invoke`` tasks did via ``infrahubctl menu load`` / ``infrahubctl run``.
    """
    env = os.environ.copy()
    env["INFRAHUB_ADDRESS"] = address
    env["INFRAHUB_API_TOKEN"] = ADMIN_API_TOKEN
    env["INFRAHUB_MAX_CONCURRENT_EXECUTION"] = "1"
    binary = shutil.which("infrahubctl") or "infrahubctl"
    result = subprocess.run(  # noqa: S603
        [binary, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"`infrahubctl {' '.join(args)}` failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result.stdout


@pytest.fixture(scope="session")
def schema_base(infrahub_client: InfrahubClientSync, infrahub_provisioned_externally: bool) -> None:
    """Load the full base schema (models/base/*.yml) as one set.

    Equivalent to `infrahubctl schema load models/base`.
    """
    if infrahub_provisioned_externally:
        return
    schemas = [
        yaml.safe_load((MODELS_DIR / "base" / filename).read_text(encoding="utf-8")) for filename in BASE_SCHEMA_FILES
    ]
    response = infrahub_client.schema.load(schemas=schemas, wait_until_converged=True)
    if response.errors:
        raise RuntimeError(f"Base schema failed to load: {response.errors}")


@pytest.fixture(scope="session")
def infrastructure_menu(
    infrahub_address: str,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> None:
    """Load the navigation menu. Equivalent to `infrahubctl menu load models/base_menu.yml`."""
    if infrahub_provisioned_externally:
        return
    _run_infrahubctl(["menu", "load", str(MODELS_DIR / "base_menu.yml")], infrahub_address)


@pytest.fixture(scope="session")
def infrastructure_data(
    infrahub_address: str,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> None:
    """Load the full demo dataset by running models/infrastructure_edge.py.

    Equivalent to `infrahubctl run models/infrastructure_edge.py`. This runs the
    exact same generator the legacy suite used (default "medium" profile: 5
    sites, 6 devices/site, BGP mesh and the 5 branch scenarios), so the dataset
    is byte-faithful to the current CI dataset rather than a reimplementation.
    """
    if infrahub_provisioned_externally:
        return
    _run_infrahubctl(
        ["run", str(MODELS_DIR / "infrastructure_edge.py")],
        infrahub_address,
        cwd=REPO_ROOT,
        timeout=INFRASTRUCTURE_DATA_TIMEOUT,
    )


@pytest.fixture(scope="session")
def demo_edge_repo(
    infrahub_address: str,
    infrahub_compose_dir: Path,
    infrastructure_data: None,
    infrahub_provisioned_externally: bool,
) -> None:
    """Register and sync the `demo-edge` external Git repository.

    Equivalent to `invoke dev.infra-git-import dev.infra-git-create`. Required by
    repository / artifact / proposed-change specs. Reuses the SDK testing GitRepo
    helper (a CoreRepositoryCreate mutation + sync polling); the repository is
    copied into the compose `repos` directory which is mounted at /remote.
    """
    if infrahub_provisioned_externally:
        return

    import asyncio

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.testing.repository import GitRepo

    remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]

    async def _add() -> None:
        client = InfrahubClient(config=Config(address=infrahub_address, api_token=ADMIN_API_TOKEN))
        repo = GitRepo(name="demo-edge", src_directory=DEMO_EDGE_REPO_FIXTURE, dst_directory=remote_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client, interval=5, retries=24)
        if not in_sync:
            raise RuntimeError("The demo-edge repository did not reach the in-sync state")

    asyncio.run(_add())


@pytest.fixture
def branch_api(infrahub_client: InfrahubClientSync) -> BranchAPI:
    """Create/merge/delete throwaway branches via the API (port of graphql.ts)."""
    return BranchAPI(infrahub_client)


# --------------------------------------------------------------------------- #
# Playwright integration: base URL + per-role authenticated pages
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def base_url(infrahub_address: str) -> str:
    """Override pytest-playwright's base_url.

    Lets relative `page.goto("/...")` calls resolve against the running Infrahub.
    """
    return infrahub_address


@pytest.fixture(scope="session")
def storage_state_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("e2e-auth")


def _build_storage_state(browser: Browser, base_url: str, path: Path, username: str, password: str) -> str:
    """Log in once via the UI and persist the session, mirroring auth.setup.ts."""
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    try:
        login(page, username, password)
        context.storage_state(path=path)
    finally:
        context.close()
    return str(path)


@pytest.fixture(scope="session")
def admin_storage_state(browser: Browser, base_url: str, storage_state_dir: Path) -> str:
    return _build_storage_state(
        browser,
        base_url,
        storage_state_dir / "admin.json",
        ADMIN_CREDENTIALS["username"],
        ADMIN_CREDENTIALS["password"],
    )


@pytest.fixture(scope="session")
def read_write_storage_state(
    browser: Browser,
    base_url: str,
    storage_state_dir: Path,
    infrastructure_data: None,
) -> str:
    return _build_storage_state(
        browser,
        base_url,
        storage_state_dir / "read-write.json",
        READ_WRITE_CREDENTIALS["username"],
        READ_WRITE_CREDENTIALS["password"],
    )


@pytest.fixture(scope="session")
def read_only_storage_state(
    browser: Browser,
    base_url: str,
    storage_state_dir: Path,
    infrastructure_data: None,
) -> str:
    return _build_storage_state(
        browser,
        base_url,
        storage_state_dir / "read-only.json",
        READ_ONLY_CREDENTIALS["username"],
        READ_ONLY_CREDENTIALS["password"],
    )


def _role_page(browser: Browser, base_url: str, storage_state: str) -> Generator[Page, None, None]:
    context = browser.new_context(base_url=base_url, storage_state=storage_state)
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture
def admin_page(browser: Browser, base_url: str, admin_storage_state: str) -> Generator[Page, None, None]:
    yield from _role_page(browser, base_url, admin_storage_state)


@pytest.fixture
def read_write_page(browser: Browser, base_url: str, read_write_storage_state: str) -> Generator[Page, None, None]:
    yield from _role_page(browser, base_url, read_write_storage_state)


@pytest.fixture
def read_only_page(browser: Browser, base_url: str, read_only_storage_state: str) -> Generator[Page, None, None]:
    yield from _role_page(browser, base_url, read_only_storage_state)

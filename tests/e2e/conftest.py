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
import time
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

# Composable demo-dataset slices built on the sync SDK (tests/e2e/data/),
# progressively replacing the script-based infrastructure_data fixture.
pytest_plugins = [
    "data.common",
    "data.rbac",
    "data.locations",
    "data.org_registry",
    "data.profiles_groups",
    "data.ipam_pools",
    "data.patch_template",
    "data.sites",
    "data.topology",
    "data.scenario_branches",
]

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from playwright.sync_api import Browser, BrowserContext, Page

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "models"
DEMO_EDGE_REPO_FIXTURE = REPO_ROOT / "backend/tests/fixtures/repos/infrahub-demo-edge/initial__main"

# How long the demo-data generator (models/infrastructure_edge.py) may run.
INFRASTRUCTURE_DATA_TIMEOUT = 30 * 60

# pytest-playwright defaults the `expect` assertion timeout to 5s. The legacy TS
# suite ran with a 60s (local) / 180s (CI) expect timeout, so async UI updates
# (toasts, table refreshes, branch/task settling) had ample time. Match that
# spirit with a generous default; individual assertions can still override.
#
# When the backend response delay is requested (INFRAHUB_TESTING_RESPONSE_DELAY), every
# GraphQL request is slowed once the delay is enabled, so widen the timeout — mirrors
# playwright.config.ts, which bumps the CI expect timeout from 3min to 6min for such runs.
# NB: the signal is INFRAHUB_TESTING_RESPONSE_DELAY, NOT the backend's INFRAHUB_MISC_RESPONSE_DELAY
# — setting the latter in the environment would slow the demo-data load at boot (see
# response_delay_enabled / InfrahubDockerCompose.set_server_response_delay).
_RESPONSE_DELAY = int(os.environ.get("INFRAHUB_TESTING_RESPONSE_DELAY") or "0")
expect.set_options(timeout=60_000 if _RESPONSE_DELAY else 30_000)


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
) -> Generator[InfrahubDockerCompose, None, None]:
    """Boot one Infrahub stack for the whole session and expose the compose handle.

    Mirrors infrahub_testcontainers.helpers.TestInfrahubDocker.infrahub_app but
    at session scope so the entire e2e suite shares a single instance (as the
    legacy TS suite did). Yields the compose object so dependents can read mapped
    ports (get_services_port) and toggle runtime settings (set_server_response_delay).
    """
    compose = InfrahubDockerCompose.init(directory=infrahub_compose_dir, version=infrahub_version)
    try:
        compose.start()
    except Exception as exc:  # pragma: no cover - surfaced with logs for debugging
        stdout, stderr = compose.get_logs()
        raise RuntimeError(f"Failed to start docker compose:\nStdout:\n{stdout}\nStderr:\n{stderr}") from exc

    yield compose

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
    compose = request.getfixturevalue("infrahub_app")
    port = compose.get_services_port()["server"]
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
    # Serialize generator execution. Higher concurrency races the demo generator against the
    # load-balanced multi-replica server and fails the load with read-after-write errors
    # ("Unable to find the node <id> / InfraDevice in the database"). Keep this at 1; do NOT
    # raise it to work around data not persisting (e.g. symmetric relationships) — fix the
    # generator instead (see find_and_connect_interfaces in models/infrastructure_edge.py).
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
    """Load the navigation menu (models/base_menu.yml) via the SDK menu spec.

    Equivalent to `infrahubctl menu load models/base_menu.yml`: MenuFile's
    validate_format + process are exactly what the CLI command calls. The menu
    helpers are async-only, so the coroutine runs in a private asyncio.run() —
    safe here because the sync suite never holds a running event loop.
    """
    if infrahub_provisioned_externally:
        return

    import asyncio

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.spec.menu import MenuFile

    async def _load_menu() -> None:
        client = InfrahubClient(config=Config(address=infrahub_address, api_token=ADMIN_API_TOKEN))
        for file in MenuFile.load_file_from_disk(path=MODELS_DIR / "base_menu.yml"):
            await file.validate_format(client=client)
            await file.process(client=client)

    asyncio.run(_load_menu())


@pytest.fixture(scope="session")
def infrastructure_data(request: pytest.FixtureRequest, infrahub_provisioned_externally: bool) -> None:
    """Load the full demo dataset through the tests/e2e/data/ SDK slices.

    Script-free replacement for `infrahubctl run models/infrastructure_edge.py`:
    the slice DAG reproduces the script's medium-profile dataset (5 sites, 6
    devices/site, BGP mesh, scenario branches), proven by a structural parity
    diff against a script-loaded stack (see tests/e2e/data/parity.py). Kept
    under the legacy fixture name so tests keep their declared dependency;
    narrowing individual domains to specific slices is incremental follow-up.
    """
    if infrahub_provisioned_externally:
        return
    request.getfixturevalue("infrastructure_data_sdk")


@pytest.fixture(scope="session")
def infrastructure_data_monolith(
    infrahub_address: str,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> None:
    """Load the demo dataset by running models/infrastructure_edge.py (legacy path).

    Kept ONLY as the reference loader for the parity dump
    (INFRAHUB_E2E_PARITY=monolith); the suite itself loads through the SDK
    slices. Equivalent to `infrahubctl run models/infrastructure_edge.py`.
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
def infrastructure_data_sdk(request: pytest.FixtureRequest) -> None:
    """The full demo dataset via the tests/e2e/data/ SDK slices — no external script.

    data_scenario_branches is the terminal node of the slice DAG: it pulls
    data_topology (which pulls data_sites, which pulls rbac/locations/
    org_registry/ipam_pools) and data_patch_template, so requesting it loads
    everything the monolithic models/infrastructure_edge.py run produced —
    minus the two scenario branches no test references (their pool consumption
    is replayed; see data/scenario_branches.py).
    """
    request.getfixturevalue("data_scenario_branches")


@pytest.fixture(scope="session")
def demo_edge_repo(
    infrahub_client: InfrahubClientSync,
    infrahub_compose_dir: Path,
    infrastructure_data: None,
    infrahub_provisioned_externally: bool,
) -> None:
    """Register and sync the `demo-edge` external Git repository (synchronous).

    Equivalent to `invoke dev.infra-git-import dev.infra-git-create`. Required by
    repository-derived specs (artifacts, the repo's GraphQL queries, generators,
    proposed-change checks). The fixture repo is copied into the compose `repos`
    directory (mounted at /remote) via the SDK GitRepo helper (its sync init does
    the copy + git init/commit), registered with a CoreRepositoryCreate mutation,
    then polled until in-sync. Synchronous on purpose — the suite has no running
    asyncio loop to host the SDK's async GitRepo helper.
    """
    if infrahub_provisioned_externally:
        return

    import time

    from infrahub_sdk.graphql import Mutation
    from infrahub_sdk.testing.repository import GitRepo

    remote_dir = infrahub_compose_dir / PROJECT_ENV_VARIABLES["INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY"]
    # GitRepo.__post_init__ runs a synchronous copy + git init/commit of the fixture repo.
    GitRepo(name="demo-edge", src_directory=DEMO_EDGE_REPO_FIXTURE, dst_directory=remote_dir)

    mutation = Mutation(
        mutation="CoreRepositoryCreate",
        input_data={"data": {"name": {"value": "demo-edge"}, "location": {"value": "/remote/demo-edge"}}},
        query={"ok": None},
    )
    infrahub_client.execute_graphql(query=mutation.render(), tracker="mutation-repository-create")

    for _ in range(30):
        repo = infrahub_client.get(kind="CoreRepository", name__value="demo-edge")
        status = repo.sync_status.value
        if status == "in-sync":
            return
        if status == "error-import":
            raise RuntimeError("The demo-edge repository import errored")
        time.sleep(5)
    raise RuntimeError("The demo-edge repository did not reach the in-sync state")


@pytest.fixture
def branch_api(infrahub_client: InfrahubClientSync) -> BranchAPI:
    """Create/merge/delete throwaway branches via the API (port of graphql.ts)."""
    return BranchAPI(infrahub_client)


# --------------------------------------------------------------------------- #
# Playwright integration: base URL + per-role authenticated pages
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    """Inject the no-netlink LD_PRELOAD shim into the browser process (CI only).

    Chromium's AddressTrackerLinux listens to netlink, and Docker/veth churn on
    CI runners floods it, causing ERR_NETWORK_CHANGED mid-navigation. The shim
    (tests/e2e/fixtures/no_netlink.c, compiled by the CI job into NO_NETLINK_SO)
    fails NETLINK_ROUTE sockets so Chromium takes its "assume always online"
    path. Scoped to the browser process via the launch env — the same pattern
    the legacy playwright.config.ts used — and a no-op locally where
    NO_NETLINK_SO is unset.
    """
    shim = os.environ.get("NO_NETLINK_SO")
    if not shim:
        return browser_type_launch_args
    return {**browser_type_launch_args, "env": {**os.environ, "LD_PRELOAD": shim}}


@pytest.fixture(scope="session")
def base_url(infrahub_address: str) -> str:
    """Override pytest-playwright's base_url.

    Lets relative `page.goto("/...")` calls resolve against the running Infrahub.
    """
    return infrahub_address


@pytest.fixture(scope="session")
def response_delay_enabled(
    request: pytest.FixtureRequest,
    infrahub_client: InfrahubClientSync,
    infrahub_provisioned_externally: bool,
) -> None:
    """Slow the backend for the browser-test phase when INFRAHUB_TESTING_RESPONSE_DELAY is set.

    Mirrors the TS e2e CI job (which loads data, then restarts the server with the delay):
    the full dataset is provisioned first — fast, since the demo-data load makes thousands of
    serialized GraphQL calls — and only then is the infrahub-server recreated with the
    per-request delay so browser flows exercise realistic loading states. No-op when the delay
    is unset or when running against an externally provisioned Infrahub. The per-role page
    fixtures depend on this so the delay is in effect before any browser interaction.

    The signal is INFRAHUB_TESTING_RESPONSE_DELAY (the package convention), deliberately NOT the
    backend's INFRAHUB_MISC_RESPONSE_DELAY: the latter is read at server startup, so putting it in
    the boot environment would slow the demo-data load. set_server_response_delay writes the
    backend var into the compose .env only after data is loaded, then recreates the server.

    infrahub_app is resolved lazily (request.getfixturevalue) AFTER the early return: a direct
    parameter would be instantiated eagerly and boot the testcontainers stack even in the
    pre-provisioned INFRAHUB_ADDRESS mode, where no container must ever start.
    """
    delay = int(os.environ.get("INFRAHUB_TESTING_RESPONSE_DELAY") or "0")
    if not delay or infrahub_provisioned_externally:
        return

    # Provision the heavy datasets BEFORE slowing the server: the demo-data load makes
    # thousands of serialized GraphQL mutations, so a boot-time delay would blow the CI
    # budget. (demo_edge_repo is intentionally not forced here — it is needed only by repo
    # specs, its registration is a handful of calls, and forcing it would couple every
    # delay-mode run to the Git fixture; it loads lazily when a repo spec requires it.)
    for fixture_name in ("schema_base", "infrastructure_menu", "infrastructure_data"):
        request.getfixturevalue(fixture_name)

    infrahub_app: InfrahubDockerCompose = request.getfixturevalue("infrahub_app")
    infrahub_app.set_server_response_delay(delay)

    # The server replicas were force-recreated; wait until the LB routes to a responsive
    # instance again (each probe now also carries the delay).
    last_exc: Exception | None = None
    for _ in range(30):
        try:
            infrahub_client.branch.all()
            return
        except Exception as exc:  # transient during recreate; re-raised below if it never recovers
            last_exc = exc
            time.sleep(2)
    raise RuntimeError(f"infrahub-server did not recover after enabling the response delay: {last_exc}")


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
def admin_storage_state(browser: Browser, base_url: str, storage_state_dir: Path, response_delay_enabled: None) -> str:
    return _build_storage_state(
        browser,
        base_url,
        storage_state_dir / "admin.json",
        ADMIN_CREDENTIALS["username"],
        ADMIN_CREDENTIALS["password"],
    )


@pytest.fixture(scope="session")
def read_write_storage_state(  # noqa: PLR0913, PLR0917  (each argument is a pytest fixture dependency)
    browser: Browser,
    base_url: str,
    storage_state_dir: Path,
    request: pytest.FixtureRequest,
    infrahub_provisioned_externally: bool,
    response_delay_enabled: None,
) -> str:
    # The cobrian account comes from the RBAC slice — pulling the whole dataset
    # just to authenticate would force the full load on every read-write test.
    if not infrahub_provisioned_externally:
        request.getfixturevalue("data_rbac")
    return _build_storage_state(
        browser,
        base_url,
        storage_state_dir / "read-write.json",
        READ_WRITE_CREDENTIALS["username"],
        READ_WRITE_CREDENTIALS["password"],
    )


@pytest.fixture(scope="session")
def read_only_storage_state(  # noqa: PLR0913, PLR0917  (each argument is a pytest fixture dependency)
    browser: Browser,
    base_url: str,
    storage_state_dir: Path,
    request: pytest.FixtureRequest,
    infrahub_provisioned_externally: bool,
    response_delay_enabled: None,
) -> str:
    # The jbauer account comes from the RBAC slice (see read_write_storage_state).
    if not infrahub_provisioned_externally:
        request.getfixturevalue("data_rbac")
    return _build_storage_state(
        browser,
        base_url,
        storage_state_dir / "read-only.json",
        READ_ONLY_CREDENTIALS["username"],
        READ_ONLY_CREDENTIALS["password"],
    )


def _role_page(new_context: Callable[..., BrowserContext], storage_state: str) -> Page:
    # Use pytest-playwright's `new_context` factory (NOT browser.new_context) so the context is
    # registered with the artifacts recorder: failures of authenticated tests then produce a
    # trace/video/screenshot under --output (retain-on-failure). base_url and record_video_dir
    # come from browser_context_args; the factory closes the context and saves artifacts at
    # test teardown, so no manual close is needed here.
    context = new_context(storage_state=storage_state)
    return context.new_page()


@pytest.fixture
def admin_page(new_context: Callable[..., BrowserContext], admin_storage_state: str) -> Page:
    return _role_page(new_context, admin_storage_state)


@pytest.fixture
def read_write_page(new_context: Callable[..., BrowserContext], read_write_storage_state: str) -> Page:
    return _role_page(new_context, read_write_storage_state)


@pytest.fixture
def read_only_page(new_context: Callable[..., BrowserContext], read_only_storage_state: str) -> Page:
    return _role_page(new_context, read_only_storage_state)

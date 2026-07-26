import asyncio
import contextlib
from urllib.parse import quote, urlencode

from prefect import flow, task
from prefect.blocks.redis import RedisStorageContainer
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.actions import VariableCreate, WorkPoolCreate
from prefect.exceptions import ObjectAlreadyExists
from prefect.logging import get_run_logger
from pydantic import SecretStr

from infrahub import config
from infrahub.config import CacheSettings
from infrahub.display_labels.gather import gather_trigger_display_labels_jinja2
from infrahub.hfid.gather import gather_trigger_hfid
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers

from .catalogue import WORKER_POOLS, get_workflows
from .models import TASK_RESULT_STORAGE_NAME

TASK_MANAGER_SETUP_MARKER = "infrahub_task_manager_setup_completed"


async def mark_task_manager_setup_completed() -> None:
    """Record in the task manager that the deployments and triggers are fully registered.

    The marker is a task-manager variable so it shares the task manager's lifecycle: a fresh task
    manager has no marker until the registration completes, while a task manager with persisted
    state keeps both the marker and the registrations across restarts.
    """
    async with get_client(sync_client=False) as client:
        if await client.read_variable_by_name(TASK_MANAGER_SETUP_MARKER) is None:
            # a concurrent registration may have created it in between; its presence is all that matters
            with contextlib.suppress(Exception):
                await client.create_variable(variable=VariableCreate(name=TASK_MANAGER_SETUP_MARKER, value="true"))


async def wait_for_task_manager_setup(max_wait_seconds: int = 180) -> None:
    """Block until the task-manager deployments and triggers are registered.

    A serving worker may receive a request that dispatches a workflow run at any moment, and the
    dispatch fails while the registration is still in flight. Workers that do not perform the
    registration themselves must therefore wait for the completion marker before finishing their
    startup and accepting traffic.

    Raises:
        RuntimeError: When the registration marker does not appear within ``max_wait_seconds``.

    """
    async with get_client(sync_client=False) as client:
        for _ in range(max(1, max_wait_seconds * 2)):
            with contextlib.suppress(Exception):  # connection errors while the task manager is still booting
                if await client.read_variable_by_name(TASK_MANAGER_SETUP_MARKER) is not None:
                    return
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Task manager setup did not complete within {max_wait_seconds}s")


async def wait_for_task_manager(max_wait_seconds: int = 120) -> None:
    """Block until the task manager (Prefect) API is reachable.

    The API server's dependency on the task manager is relaxed to ``service_started`` so the schema
    load can overlap the (slow) task manager boot. Registering deployments and triggers still needs a
    reachable API, so callers wait here first.

    Raises:
        RuntimeError: When the task manager is not reachable within ``max_wait_seconds`` seconds.

    """
    async with get_client(sync_client=False) as client:
        for _ in range(max(1, max_wait_seconds * 2)):
            with contextlib.suppress(Exception):  # any connection error means the API is not up yet
                if await client.api_healthcheck() is None:
                    return
            await asyncio.sleep(0.5)
    raise RuntimeError(f"Task manager (Prefect) did not become reachable within {max_wait_seconds}s")


def build_cache_connection_string(cache: CacheSettings) -> str:
    """Build a redis:// or rediss:// URL from cache settings.

    All TLS knobs propagate through redis.Redis.from_url: the scheme selects
    SSLConnection, and ssl_cert_reqs / ssl_check_hostname / ssl_ca_certs query
    params are passed through to the connection. This keeps the Prefect result
    storage block in parity with lock.py and the cache adapter, which read the
    same INFRAHUB_CACHE_TLS_* settings directly.

    Raises:
        ValueError: When ``INFRAHUB_CACHE_USERNAME`` is set without ``INFRAHUB_CACHE_PASSWORD``.

    """
    if cache.username and not cache.password:
        raise ValueError("INFRAHUB_CACHE_USERNAME is set but INFRAHUB_CACHE_PASSWORD is not. Both are required.")

    scheme = "rediss" if cache.tls_enabled else "redis"

    userinfo = ""
    if cache.username and cache.password:
        userinfo = f"{quote(cache.username, safe='')}:{quote(cache.password, safe='')}@"
    elif cache.password:
        userinfo = f":{quote(cache.password, safe='')}@"

    query: dict[str, str] = {}
    if cache.tls_enabled:
        if cache.tls_insecure:
            query["ssl_cert_reqs"] = "none"
            query["ssl_check_hostname"] = "False"
        if cache.tls_ca_file:
            query["ssl_ca_certs"] = cache.tls_ca_file

    qs = f"?{urlencode(query)}" if query else ""
    return f"{scheme}://{userinfo}{cache.address}:{cache.service_port}/{cache.database}{qs}"


@task(name="task-manager-setup-worker-pools", task_run_name="Setup Worker pools", cache_policy=NONE)
async def setup_worker_pools(client: PrefectClient) -> None:
    log = get_run_logger()
    for worker in WORKER_POOLS:
        wp = WorkPoolCreate(
            name=worker.name,
            type=worker.worker_type or config.SETTINGS.workflow.default_worker_type,
            description=worker.description,
        )

        try:
            await client.create_work_pool(work_pool=wp, overwrite=True)
            log.info(f"Work pool {worker.name} created successfully ... ")
        except ObjectAlreadyExists:
            log.warning(f"Work pool {worker.name} already present ")


@task(name="task-manager-setup-deployments", task_run_name="Setup Deployments", cache_policy=NONE)
async def setup_deployments(client: PrefectClient) -> None:
    log = get_run_logger()
    for workflow in get_workflows():
        # For now the workpool is hardcoded but
        # later we need to make it dynamic to have a different worker based on the type of the workflow
        work_pool = WORKER_POOLS[0]
        await workflow.save(client=client, work_pool=work_pool)
        log.info(f"Flow {workflow.name}, created successfully ... ")


@task(name="task-manager-setup-blocks", task_run_name="Setup Blocks", cache_policy=NONE)
async def setup_blocks() -> None:
    log = get_run_logger()

    try:
        await RedisStorageContainer.aregister_type_and_schema()
    except ObjectAlreadyExists:
        log.warning(f"Redis Storage {TASK_RESULT_STORAGE_NAME} already registered ")

    redis_block = RedisStorageContainer(
        connection_string=SecretStr(build_cache_connection_string(config.SETTINGS.cache))
    )
    try:
        await redis_block.asave(name=TASK_RESULT_STORAGE_NAME, overwrite=True)
    except ObjectAlreadyExists:
        log.warning(f"Redis Storage {TASK_RESULT_STORAGE_NAME} already present ")


@flow(name="task-manager-setup", flow_run_name="Setup Task Manager")
async def setup_task_manager() -> None:
    async with get_client(sync_client=False) as client:
        await setup_blocks()
        await setup_worker_pools(client=client)
        await setup_deployments(client=client)
        await setup_triggers(
            client=client, triggers=builtin_triggers, trigger_type=TriggerType.BUILTIN, force_update=True
        )


@flow(name="task-manager-identifiers", flow_run_name="Setup Task Manager Display Labels and HFID")
async def setup_task_manager_identifiers() -> None:
    async with get_client(sync_client=False) as client:
        display_label_triggers = await gather_trigger_display_labels_jinja2()
        await setup_triggers(
            client=client,
            triggers=display_label_triggers,
            trigger_type=TriggerType.DISPLAY_LABEL_JINJA2,
            force_update=True,
        )
        hfid_triggers = await gather_trigger_hfid()
        await setup_triggers(
            client=client,
            triggers=hfid_triggers,
            trigger_type=TriggerType.HUMAN_FRIENDLY_ID,
            force_update=True,
        )

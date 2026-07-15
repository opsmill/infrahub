from urllib.parse import quote, urlencode

from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectAlreadyExists
from prefect.logging import get_run_logger
from prefect_redis import RedisDatabase
from pydantic import SecretStr

from infrahub import config
from infrahub.config import CacheSettings
from infrahub.display_labels.gather import gather_trigger_display_labels_jinja2
from infrahub.hfid.gather import gather_trigger_hfid
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers

from .catalogue import WORKER_POOLS, get_workflows
from .constants import WorkflowPriority
from .models import TASK_RESULT_STORAGE_NAME


def _redis_url(*, scheme: str, host: str, port: int, db: int, conn: dict[str, object]) -> str:
    """Assemble a redis://|rediss:// URL with redis-py-native ssl_* query params."""
    userinfo = ""
    username = conn.get("username")
    password = conn.get("password")
    if username and password:
        userinfo = f"{quote(str(username), safe='')}:{quote(str(password), safe='')}@"
    elif password:
        userinfo = f":{quote(str(password), safe='')}@"

    query: dict[str, str] = {}
    if conn.get("ssl"):
        if conn.get("ssl_cert_reqs") == "none":
            query["ssl_cert_reqs"] = "none"
        if conn.get("ssl_check_hostname") is False:
            query["ssl_check_hostname"] = "False"
        if conn.get("ssl_ca_certs"):
            query["ssl_ca_certs"] = str(conn["ssl_ca_certs"])

    qs = f"?{urlencode(query)}" if query else ""
    return f"{scheme}://{userinfo}{host}:{port}/{db}{qs}"


def build_cache_connection_string(cache: CacheSettings) -> str:
    """Build the Redis connection URL for Prefect's result-storage block from cache settings.

    The result-storage block understands the full redis://, rediss://, redis+sentinel:// and
    rediss+sentinel:// grammar, so a configured ``cache.url`` (single-node or Sentinel, with any TLS
    query parameters) is passed through unchanged and follows master failover just like the cache and
    lock connections. When no URL is set the scalar connection settings are assembled into a
    single-node redis://|rediss:// URL.

    Raises:
        ValueError: When ``INFRAHUB_CACHE_USERNAME`` is set without ``INFRAHUB_CACHE_PASSWORD``.

    """
    if cache.url is not None:
        return cache.url.get_secret_value()

    if cache.username and not cache.password:
        raise ValueError("INFRAHUB_CACHE_USERNAME is set but INFRAHUB_CACHE_PASSWORD is not. Both are required.")

    scheme = "rediss" if cache.tls_enabled else "redis"
    conn: dict[str, object] = {
        "username": cache.username,
        "password": cache.password,
        "ssl": cache.tls_enabled,
        "ssl_cert_reqs": "none" if cache.tls_insecure else "optional",
        "ssl_check_hostname": not cache.tls_insecure,
        "ssl_ca_certs": cache.tls_ca_file,
    }
    return _redis_url(scheme=scheme, host=cache.address, port=cache.service_port, db=cache.database, conn=conn)


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


@task(name="task-manager-setup-work-queues", task_run_name="Setup Work queues", cache_policy=NONE)
async def setup_work_queues(client: PrefectClient) -> None:
    log = get_run_logger()
    for pool in WORKER_POOLS:
        for priority in WorkflowPriority:
            try:
                await client.create_work_queue(
                    name=priority.queue_name,
                    priority=priority.queue_priority,
                    work_pool_name=pool.name,
                )
                log.info(f"Work queue {priority.queue_name} created successfully on pool {pool.name} ... ")
            except ObjectAlreadyExists:
                work_queue = await client.read_work_queue_by_name(name=priority.queue_name, work_pool_name=pool.name)
                await client.update_work_queue(id=work_queue.id, priority=priority.queue_priority)
                log.info(f"Work queue {priority.queue_name} already present on pool {pool.name}, priority updated ")


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
        await RedisDatabase.aregister_type_and_schema()
    except ObjectAlreadyExists:
        log.warning(f"Redis Storage {TASK_RESULT_STORAGE_NAME} already registered ")

    redis_block = RedisDatabase(connection_url=SecretStr(build_cache_connection_string(config.SETTINGS.cache)))
    try:
        await redis_block.asave(name=TASK_RESULT_STORAGE_NAME, overwrite=True)
    except ObjectAlreadyExists:
        log.warning(f"Redis Storage {TASK_RESULT_STORAGE_NAME} already present ")


@flow(name="task-manager-setup", flow_run_name="Setup Task Manager")
async def setup_task_manager() -> None:
    async with get_client(sync_client=False) as client:
        await setup_blocks()
        await setup_worker_pools(client=client)
        await setup_work_queues(client=client)
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

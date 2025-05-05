from prefect import flow, task
from prefect.blocks.redis import RedisStorageContainer
from prefect.cache_policies import NONE
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectAlreadyExists
from prefect.logging import get_run_logger

from infrahub import config
from infrahub.trigger.catalogue import builtin_triggers
from infrahub.trigger.models import TriggerType
from infrahub.trigger.setup import setup_triggers

from .catalogue import worker_pools, workflows
from .models import TASK_RESULT_STORAGE_NAME


@task(name="task-manager-setup-worker-pools", task_run_name="Setup Worker pools", cache_policy=NONE)  # type: ignore[arg-type]
async def setup_worker_pools(client: PrefectClient) -> None:
    log = get_run_logger()
    for worker in worker_pools:
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


@task(name="task-manager-setup-deployments", task_run_name="Setup Deployments", cache_policy=NONE)  # type: ignore[arg-type]
async def setup_deployments(client: PrefectClient) -> None:
    log = get_run_logger()
    for workflow in workflows:
        # For now the workpool is hardcoded but
        # later we need to make it dynamic to have a different worker based on the type of the workflow
        work_pool = worker_pools[0]
        await workflow.save(client=client, work_pool=work_pool)
        log.info(f"Flow {workflow.name}, created successfully ... ")


@task(name="task-manager-setup-blocks", task_run_name="Setup Blocks", cache_policy=NONE)  # type: ignore[arg-type]
async def setup_blocks() -> None:
    log = get_run_logger()

    try:
        await RedisStorageContainer.register_type_and_schema()
    except ObjectAlreadyExists:
        log.warning(f"Redis Storage {TASK_RESULT_STORAGE_NAME} already registered ")

    redis_block = RedisStorageContainer.from_host(
        host=config.SETTINGS.cache.address,
        port=config.SETTINGS.cache.service_port,
        db=config.SETTINGS.cache.database,
        username=config.SETTINGS.cache.username or None,
        password=config.SETTINGS.cache.password or None,
    )
    try:
        await redis_block.save(name=TASK_RESULT_STORAGE_NAME, overwrite=True)
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

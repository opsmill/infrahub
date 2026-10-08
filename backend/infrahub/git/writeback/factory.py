from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from infrahub import config, lock
from infrahub.auth.session import AnonymousSession
from infrahub.context import InfrahubContext
from infrahub.core.merge.builder import build_held_regeneration_releaser
from infrahub.core.registry import registry
from infrahub.git.writeback.constants import LOCAL_GIT_TIMEOUT_SECONDS
from infrahub.git.writeback.git_adapter import RepositoryDeliveryGitAdapter
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.recovery import DeliveryRecoveryCheck
from infrahub.git.writeback.runs import PrefectDeliveryRunQuery
from infrahub.git.writeback.service import RepositoryWritebackService
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.log import get_log_data
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_message_bus, get_workflow

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from prefect.client.orchestration import PrefectClient

    from infrahub.database import InfrahubDatabase
    from infrahub.git.repository import InfrahubRepository


async def build_writeback_service(
    *,
    db: InfrahubDatabase,
    repository: InfrahubRepository,
    context: InfrahubContext,
    log: Logger | LoggerAdapter[Logger],
) -> RepositoryWritebackService:
    """Build the delivery service of the repository, with its Git adapter bound to the same repository.

    Args:
        db: A session that the flow opened for the life of the service.
        context: The context of the regeneration that a delivery releases.

    """
    default_branch = await registry.get_branch(db=db)
    clock = partial(datetime.now, UTC)
    state = WritebackIntentStore(db=db, lock_registry=lock.registry, default_branch=default_branch, clock=clock)
    return RepositoryWritebackService(
        repository=RepositoryRef(
            id=str(repository.id), name=repository.name, destination_git_branch=repository.default_branch
        ),
        state=state,
        git=RepositoryDeliveryGitAdapter(
            repository=repository,
            destination_branch=default_branch.name,
            destination_branch_id=str(default_branch.get_uuid()),
            message_bus=await get_message_bus(),
            initiator_id=WORKER_IDENTITY,
            request_id=get_log_data().get("request_id", ""),
            use_explicit_merge_commit=config.SETTINGS.git.use_explicit_merge_commit,
            local_timeout_seconds=LOCAL_GIT_TIMEOUT_SECONDS,
        ),
        releaser=await build_held_regeneration_releaser(
            db=db, state=state, default_branch=default_branch, context=context, log=log
        ),
        lock_registry=lock.registry,
        clock=clock,
    )


async def build_recovery_check(*, db: InfrahubDatabase, prefect_client: PrefectClient) -> DeliveryRecoveryCheck:
    """Build the check that starts a delivery run of a repository whose delivery lost its attempt.

    Args:
        db: A session that the caller keeps open for the life of the check.
        prefect_client: A client that the caller keeps open for the life of the check.

    """
    default_branch = await registry.get_branch(db=db)
    clock = partial(datetime.now, UTC)
    return DeliveryRecoveryCheck(
        state=WritebackIntentStore(db=db, lock_registry=lock.registry, default_branch=default_branch, clock=clock),
        workflow=get_workflow(),
        runs=PrefectDeliveryRunQuery(client=PrefectClientAdapter(prefect_client)),
        lock_registry=lock.registry,
        clock=clock,
        context=InfrahubContext.init(branch=default_branch, account=AnonymousSession()),
    )

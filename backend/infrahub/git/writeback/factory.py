from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from infrahub import config, lock
from infrahub.core.merge.builder import build_held_regeneration_releaser
from infrahub.core.registry import registry
from infrahub.git.writeback.abandoner import WritebackAbandoner
from infrahub.git.writeback.constants import LOCAL_GIT_TIMEOUT_SECONDS
from infrahub.git.writeback.git_adapter import RepositoryDeliveryGitAdapter
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.service import RepositoryWritebackService
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.log import get_log_data
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_message_bus

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from infrahub.context import InfrahubContext
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
    return await _build(RepositoryWritebackService, db=db, repository=repository, context=context, log=log)


async def build_writeback_abandoner(
    *,
    db: InfrahubDatabase,
    repository: InfrahubRepository,
    context: InfrahubContext,
    log: Logger | LoggerAdapter[Logger],
) -> WritebackAbandoner:
    """Build the abandoner of the repository, with its delivery state, Git adapter and regeneration releaser.

    Args:
        db: A session that the flow opened for the life of the abandoner.
        context: The context of the regeneration that an abandonment releases.

    """
    return await _build(WritebackAbandoner, db=db, repository=repository, context=context, log=log)


async def _build[ComponentT: (RepositoryWritebackService, WritebackAbandoner)](
    component: type[ComponentT],
    *,
    db: InfrahubDatabase,
    repository: InfrahubRepository,
    context: InfrahubContext,
    log: Logger | LoggerAdapter[Logger],
) -> ComponentT:
    default_branch = await registry.get_branch(db=db)
    clock = partial(datetime.now, UTC)
    state = WritebackIntentStore(db=db, lock_registry=lock.registry, default_branch=default_branch, clock=clock)
    return component(
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

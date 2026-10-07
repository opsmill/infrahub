from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, override

from infrahub import config, lock
from infrahub.core.registry import registry
from infrahub.git.writeback.constants import LOCAL_GIT_TIMEOUT_SECONDS
from infrahub.git.writeback.git_adapter import RepositoryDeliveryGitAdapter
from infrahub.git.writeback.ports import RegenerationReleasePort, RepositoryRef
from infrahub.git.writeback.service import RepositoryWritebackService
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.log import get_log_data
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_message_bus

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.database import InfrahubDatabase
    from infrahub.git.repository import InfrahubRepository
    from infrahub.git.writeback.models import HeldRegeneration


class NoRegenerationReleaser(RegenerationReleasePort):
    """A release that dispatches nothing."""

    @override
    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None:
        # No barrier holds regeneration back yet, so the merge follow-ups already dispatched it.
        return


async def build_writeback_service(
    *, db: InfrahubDatabase, repository: InfrahubRepository
) -> RepositoryWritebackService:
    """Build the delivery service of the repository, with its Git adapter bound to the same repository.

    Args:
        db: A session that the flow opened for the life of the service.

    """
    default_branch = await registry.get_branch(db=db)
    clock = partial(datetime.now, UTC)
    return RepositoryWritebackService(
        repository=RepositoryRef(
            id=str(repository.id), name=repository.name, destination_git_branch=repository.default_branch
        ),
        state=WritebackIntentStore(db=db, lock_registry=lock.registry, default_branch=default_branch, clock=clock),
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
        releaser=NoRegenerationReleaser(),
        lock_registry=lock.registry,
        clock=clock,
    )

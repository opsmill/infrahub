from prefect import flow

from infrahub import lock
from infrahub.core.constants import RepositoryOperationalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import (
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
    RepositoryPermissionError,
)
from infrahub.git.convergence import InitializedRepositoryLoader, WorktreeConverger
from infrahub.git.remote_refs import ensure_branch_exists, ensure_write_access, list_remote_refs
from infrahub.git.repository import get_initialized_repo
from infrahub.git.state.warm_up import fetch_if_never_fetched
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.message_bus.messages.git_repository_connectivity import (
    GitRepositoryConnectivityResponse,
    GitRepositoryConnectivityResponseData,
)
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_client, get_message_bus

log = get_logger()


@flow(name="git-repository-check-connectivity", flow_run_name="Check connectivity for {message.repository_name}")
async def connectivity(message: messages.GitRepositoryConnectivity) -> None:
    response_data = GitRepositoryConnectivityResponseData(
        message="Successfully accessed repository",
        success=True,
        operational_status=RepositoryOperationalStatus.ONLINE.value,
    )

    try:
        refs = list_remote_refs(name=message.repository_name, url=message.repository_location)
        if message.default_branch is not None:
            ensure_branch_exists(
                refs,
                branch_name=message.default_branch,
                repository_name=message.repository_name,
                location=message.repository_location,
            )
        if message.requires_write:
            ensure_write_access(name=message.repository_name, url=message.repository_location)
    except RepositoryError as exc:
        log.exception(
            "Repository connectivity, branch or write-access check failed", repository=message.repository_name
        )
        response_data.success = False
        response_data.message = exc.message
        response_data.operational_status = {
            RepositoryConnectionError: RepositoryOperationalStatus.ERROR_CONNECTION,
            RepositoryCredentialsError: RepositoryOperationalStatus.ERROR_CRED,
            RepositoryPermissionError: RepositoryOperationalStatus.ERROR_CRED,
        }.get(type(exc), RepositoryOperationalStatus.ERROR).value

    if message.reply_requested:
        response = GitRepositoryConnectivityResponse(
            data=response_data,
        )
        message_bus = await get_message_bus()
        await message_bus.reply_if_initiator_meta(message=response, initiator=message)


@flow(name="refresh-git-clone", flow_run_name="Clone git repository {message.repository_name} on " + WORKER_IDENTITY)
async def clone(message: messages.RefreshGitClone) -> None:
    """Create this worker's local copy if it has none, and fetch a copy never fetched, without moving any local branch."""
    if message.meta and message.meta.initiator_id == WORKER_IDENTITY:
        log.info("Ignoring git clone request originating from self", worker=WORKER_IDENTITY)
        return

    repo = await get_initialized_repo(
        client=get_client(),
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
        infrahub_branch_name=message.infrahub_branch_name,
    )
    await fetch_if_never_fetched(
        repo=repo, lock=lock.registry.get(name=message.repository_name, namespace="repository")
    )


@flow(name="refresh-git-fetch", flow_run_name="Fetch git repository {message.repository_name} on " + WORKER_IDENTITY)
async def fetch(message: messages.RefreshGitFetch) -> None:
    converger = WorktreeConverger(
        lock_registry=lock.registry,
        loader=InitializedRepositoryLoader(client_provider=get_client),
        worker_identity=WORKER_IDENTITY,
    )
    await converger.converge(message)


@flow(
    name="refresh-git-repository-branch-deleted",
    flow_run_name="Delete local branch {message.branch_name} in {message.repository_name} on " + WORKER_IDENTITY,
)
async def branch_deleted(message: messages.RefreshGitRepositoryBranchDeleted) -> None:
    repo = await get_initialized_repo(
        client=get_client(),
        repository_id=message.repository_id,
        name=message.repository_name,
        repository_kind=message.repository_kind,
        # The branch this message names has just been deleted, so the repository node can only be
        # read on the default branch.
        infrahub_branch_name=registry.default_branch,
    )
    await repo.delete_local_branch(branch_name=message.branch_name)

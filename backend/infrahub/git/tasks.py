from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, assert_never

from git.exc import InvalidGitRepositoryError
from infrahub_sdk import InfrahubClient
from infrahub_sdk.branch import BranchData
from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactDefinition,
    CoreCheckDefinition,
    CoreFileCheck,
    CoreGenericRepository,
    CoreProposedChange,
    CoreReadOnlyRepository,
    CoreRepository,
    CoreRepositoryValidator,
    CoreStandardCheck,
    CoreUserValidator,
)
from infrahub_sdk.uuidt import UUIDT
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.context import InfrahubContext
from infrahub.core.constants import (
    InfrahubKind,
    RepositoryInternalStatus,
    RepositoryOperationalStatus,
    RepositorySyncStatus,
    Severity,
    ValidatorConclusion,
)
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.exceptions import (
    CheckError,
    CommitNotFoundError,
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
)
from infrahub.git.commit_id import readable_commit
from infrahub.git.graphql_queries import GitRepositoryNodeQuery
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.messages.refresh_git_fetch import BranchCommitPair
from infrahub.services.adapters.message_bus import InfrahubMessageBus
from infrahub.validators.tasks import start_validator
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import (
    get_cache,
    get_client,
    get_database,
    get_event_service,
    get_message_bus,
    get_workflow,
)

from ..core.timestamp import Timestamp
from ..core.validators.checks_runner import run_checks_and_update_validator
from ..log import get_log_data, get_logger
from ..tasks.artifact import define_artifact
from ..workflows.catalogue import (
    GIT_REPOSITORY_IMPORT_STATUS_CHECKS_RUN,
    GIT_REPOSITORY_MERGE_CONFLICTS_CHECKS_RUN,
    GIT_REPOSITORY_USER_CHECK_RUN,
    GIT_REPOSITORY_USER_CHECKS_DEFINITIONS_TRIGGER,
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_ARTIFACT_GENERATE,
)
from ..workflows.utils import add_branch_tag, add_tags
from .branch_status import accepts_commit_write
from .constants import IMPORT_STATUS_CHECK_KIND, IMPORT_STATUS_CHECK_NAME, MERGE_CONFLICT_CHECK_KIND
from .divergence.models import ReconciledBranch
from .divergence.recorder import HistoryRewriteRecorder
from .divergence.store import SdkRepositoryRecordStore, SdkTrackedTargetReader
from .divergence.suppression import RetargetMarkers
from .models import (
    CheckRepositoryImportStatus,
    CheckRepositoryMergeConflicts,
    GitDiffNamesOnly,
    GitDiffNamesOnlyResponse,
    GitReadOnlyRepositoryImportCommit,
    GitRepositoryAdd,
    GitRepositoryAddReadOnly,
    GitRepositoryImportObjects,
    GitRepositoryMerge,
    GitRepositoryPullReadOnly,
    RepositoryData,
    RequestArtifactDefinitionGenerate,
    RequestArtifactGenerate,
    TriggerRepositoryInternalChecks,
    TriggerRepositoryUserChecks,
    UserCheckData,
    UserCheckDefinitionData,
)
from .repository import InfrahubReadOnlyRepository, InfrahubRepository, PendingObjectImport, get_initialized_repo
from .sync import (
    RepositoryAdder,
    RepositoryBranchesFailedError,
    RepositoryFileImporter,
    RepositorySyncer,
    SyncOutcome,
    SyncReport,
    import_branch,
    raise_if_branches_failed,
)
from .sync_status import BranchImportVerdict, RepositoryBranchSyncStatusReader, classify_branch_import
from .utils import fetch_artifact_definition_targets, fetch_check_definition_targets, get_repositories_commit_per_branch
from .writeback.ports import DeliveryStatePort
from .writeback.store import build_intent_store


def log_skipped_branches(repo: InfrahubRepository, report: SyncReport) -> None:
    """Record every skipped remote branch of the run as a warning in the current flow run's log."""
    log = get_run_logger()
    for branch_name in report.skipped_branches:
        log.warning(
            f"Skipped remote branch '{branch_name}' of repository {repo.name}: its name collides with the "
            f"Infrahub default branch, which is mapped to this repository's default branch '{repo.default_branch}'."
        )


def format_check_log_entry(entry: dict[str, Any]) -> str:
    """Render one user-check log record as a single line for the Prefect flow logger."""
    parts = [f"[{entry['level']}] {entry['message']}"]
    object_type = entry.get("object_type")
    object_id = entry.get("object_id")
    if object_type or object_id:
        details = []
        if object_type:
            details.append(f"object_type={object_type}")
        if object_id:
            details.append(f"object_id={object_id}")
        parts.append(f"({', '.join(details)})")
    return " ".join(parts)


@dataclass(frozen=True, kw_only=True)
class ImportStatusOutcome:
    """The check result derived from the synchronization status of a repository on a branch."""

    conclusion: ValidatorConclusion
    severity: Severity
    message: str


def evaluate_import_status(
    *,
    sync_status: RepositorySyncStatus | None,
    internal_status: RepositoryInternalStatus,
    repository_name: str,
    branch_name: str,
) -> ImportStatusOutcome:
    """Decide whether the objects of a repository are usable on a branch.

    `sync_status` is the status written on the branch itself, or None when the branch only inherits one.
    """
    match classify_branch_import(sync_status=sync_status, internal_status=internal_status):
        case BranchImportVerdict.USABLE:
            return ImportStatusOutcome(conclusion=ValidatorConclusion.SUCCESS, severity=Severity.INFO, message="")
        case BranchImportVerdict.FAILED:
            message = (
                f"The last import of the objects from repository '{repository_name}' on branch '{branch_name}' "
                f"failed, so the objects registered for this repository do not match the content of the branch. "
                f"Merging would apply the rest of the branch without them. Review the latest 'Import objects' task "
                f"for this repository, resolve the cause and run the checks again."
            )
        case BranchImportVerdict.INCOMPLETE:
            message = (
                f"No completed import of the objects from repository '{repository_name}' is recorded on branch "
                f"'{branch_name}', so the objects registered for this repository may not match the content of the "
                f"branch. Wait for the import to complete, or run 'Reimport current commit' for this repository on "
                f"the branch if it does not, then run the checks again."
            )
        case _ as unreachable:
            assert_never(unreachable)

    return ImportStatusOutcome(conclusion=ValidatorConclusion.FAILURE, severity=Severity.CRITICAL, message=message)


@flow(
    name="git-repository-add-read-write",
    flow_run_name="Adding repository {model.repository_name} in branch {model.infrahub_branch_name}",
)
async def add_git_repository(model: GitRepositoryAdd) -> None:
    """Add a repository, synchronize its branches and notify the other workers.

    A failed default-branch import does not stop the other branches from synchronizing. When they all
    synchronize, the flow notifies the other workers and then fails with the default-branch error.

    Raises:
        RepositoryImportError: When the import of the default branch failed and every other branch
            synchronized.
        RepositoryBranchesFailedError: When at least one other branch failed to synchronize; the other
            workers are not notified, and a failed default-branch import is reported only in the log.

    """
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])

    client = get_client()
    database = await get_database()
    importer = RepositoryFileImporter()
    async with database.start_session() as db:
        syncer = RepositorySyncer(
            lock_registry=lock.registry,
            importer=importer,
            recorder=HistoryRewriteRecorder(store=SdkRepositoryRecordStore(client=client)),
            retarget_markers=RetargetMarkers(cache=await get_cache()),
            state=await build_intent_store(db=db, lock_registry=lock.registry),
        )
        added = await RepositoryAdder(lock_registry=lock.registry, importer=importer, client=client).add(model)
        repo = added.repository

        if model.internal_status != RepositoryInternalStatus.ACTIVE.value:
            if added.import_error:
                raise added.import_error
            return

        outcome = await syncer.sync(repo)
    log_skipped_branches(repo=repo, report=outcome.report)
    raise_if_branches_failed(repo=repo, outcome=outcome)

    try:
        pinned_commit: str | None = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
    except (ValueError, InvalidGitRepositoryError):
        pinned_commit = None
    # Notify other workers they need to clone the repository and check out the SHA pinned
    # by this initial sync, so the whole pool converges even if upstream advances meanwhile.
    notification = messages.RefreshGitFetch(
        meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
        location=model.location,
        repository_id=model.repository_id,
        repository_name=model.repository_name,
        repository_kind=InfrahubKind.REPOSITORY,
        infrahub_branch_name=model.infrahub_branch_name,
        infrahub_branch_id=model.infrahub_branch_id,
        commit=pinned_commit,
    )
    message_bus = await get_message_bus()
    await message_bus.send(message=notification)

    if added.import_error:
        raise added.import_error


@flow(
    name="git-repository-add-read-only",
    flow_run_name="Adding read only repository {model.repository_name} in branch {model.infrahub_branch_name}",
)
async def add_git_repository_read_only(model: GitRepositoryAddReadOnly) -> None:
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])

    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        repo = await InfrahubReadOnlyRepository.new(
            id=model.repository_id,
            name=model.repository_name,
            location=model.location,
            client=get_client(),
            ref=model.ref,
            infrahub_branch_name=model.infrahub_branch_name,
        )
        await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name)  # type: ignore[call-overload]
        if model.internal_status == RepositoryInternalStatus.ACTIVE.value:
            # Resolve the ref to a concrete commit once so the sync and the broadcast share the
            # same SHA; broadcasting nothing would leave workers to re-resolve the ref and diverge.
            pinned_commit: str | None = None
            if repo.ref:
                pinned_commit = repo.get_commit_value(branch_name=repo.ref, remote=True)
            await repo.sync_from_remote(commit=pinned_commit)

            # Notify other workers they need to clone the repository and check out the resolved commit
            notification = messages.RefreshGitFetch(
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                location=model.location,
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                infrahub_branch_name=model.infrahub_branch_name,
                infrahub_branch_id=model.infrahub_branch_id,
                commit=pinned_commit,
            )
            message_bus = await get_message_bus()
            await message_bus.send(message=notification)


@flow(name="git-repositories-create-branch", flow_run_name="Create branch '{branch}' in Git Repositories")
async def create_branch(branch: str, branch_id: str) -> None:
    """Request to the creation of git branches in available repositories."""
    await add_tags(branches=[branch])

    client = get_client()

    repo_query = GitRepositoryNodeQuery()
    response = await client.execute_graphql(query=repo_query.render_query())
    repositories = repo_query.parse_response(response=response)
    batch = await client.create_batch()
    for repository in repositories:
        batch.add(
            task=git_branch_create,
            client=client,
            branch=branch,
            branch_id=branch_id,
            repository_name=repository.name,
            repository_id=repository.id,
            repository_location=repository.location,
            message_bus=await get_message_bus(),
        )

    async for _, _ in batch.execute():
        pass


@flow(name="git-repositories-delete-branch", flow_run_name="Delete git branch '{branch}'")
async def delete_git_branch(branch: str) -> None:
    """Fan out branch deletion across all CoreRepository instances."""
    client = get_client()
    repo_query = GitRepositoryNodeQuery()
    response = await client.execute_graphql(query=repo_query.render_query())
    repositories = repo_query.parse_response(response=response)
    batch = await client.create_batch()
    for repository in repositories:
        batch.add(
            task=git_branch_delete,
            client=client,
            branch=branch,
            repository_name=repository.name,
            repository_id=repository.id,
            repository_location=repository.location,
        )
    async for _, _ in batch.execute():
        pass


# Only the in-process caller reads the outcome, so storing it would write one result per repository per cycle.
@flow(name="sync-git-repo-with-origin", flow_run_name="Sync git repo with origin", persist_result=False)
async def sync_git_repo_with_origin_and_tag_on_failure(
    client: InfrahubClient,
    repository_id: str,
    repository_name: str,
    repository_location: str,
    operational_status: str,
    infrahub_branch: str,
    staging_branch: str | None = None,
    graph_commits: dict[str, str | None] | None = None,
) -> SyncOutcome:
    """Synchronize one repository, linking the run to it when there is something to see there.

    A run is linked when it imports a branch, when it reports a skipped branch, or when it fails while
    the repository is online. A successful run where nothing moved on the remote is not linked.

    Raises:
        RepositoryBranchesFailedError: When at least one branch failed to synchronize.
        RepositoryError: When the repository cannot be read or synchronized.
        CommitNotFoundError: When a commit the sync needs cannot be found.

    """
    database = await get_database()
    async with database.start_session() as db:
        syncer = RepositorySyncer(
            lock_registry=lock.registry,
            importer=RepositoryFileImporter(),
            recorder=HistoryRewriteRecorder(store=SdkRepositoryRecordStore(client=client)),
            retarget_markers=RetargetMarkers(cache=await get_cache()),
            state=await build_intent_store(db=db, lock_registry=lock.registry),
        )
        online = operational_status == RepositoryOperationalStatus.ONLINE.value
        try:
            # Constructed inside the handler: it reads the repository node, so a failing read has to be
            # tagged with the repository like any other sync failure.
            repo = await InfrahubRepository.init(
                id=repository_id,
                name=repository_name,
                location=repository_location,
                client=client,
                infrahub_branch_name=infrahub_branch,
            )
        except (RepositoryError, CommitNotFoundError):
            if online:
                await add_tags(branches=[infrahub_branch], nodes=[str(repository_id)])
            raise

        try:
            outcome = await syncer.sync(repo, staging_branch=staging_branch, graph_commits=graph_commits)
        except (RepositoryError, CommitNotFoundError):
            if online:
                await add_tags(branches=[infrahub_branch], nodes=[str(repository_id)])
            raise
    await report_sync_run(
        repo=repo, report=outcome.report, infrahub_branch=infrahub_branch, link_run=online and bool(outcome.failed)
    )
    raise_if_branches_failed(repo=repo, outcome=outcome)
    return outcome


async def report_sync_run(repo: InfrahubRepository, report: SyncReport, infrahub_branch: str, link_run: bool) -> None:
    """Log the run's skipped branches when it moved something, and link the run when there is a reason to.

    Every tag update is rebuilt from the tags the run started with, so the call carries the branches
    the imports tagged the run with as well, or it would drop them.
    """
    if report.reports_skipped_branches:
        log_skipped_branches(repo=repo, report=report)
    if report.reports_skipped_branches or link_run:
        await add_tags(branches=[infrahub_branch, *report.attempted_import_branches], nodes=[str(repo.id)])


def select_writable_branch_commits(
    branch_commits: Mapping[str, str | None], branches: Mapping[str, BranchData]
) -> dict[str, str | None]:
    """Keep the commit of each Infrahub branch that can still record one.

    A branch whose status rejects a commit, and a branch Infrahub no longer lists, would be selected
    for one again on every cycle.
    """
    return {
        name: commit
        for name, commit in branch_commits.items()
        if name in branches and accepts_commit_write(branches[name])
    }


def resolve_initial_import_branch(repo: InfrahubRepository, init_failed: bool) -> str | None:
    """Return the git branch whose objects must be seeded after a clone, or None when none is needed.

    A freshly created or re-cloned local copy needs its default branch imported into the graph; an
    already-present clone does not. The branch is taken from the repository's own default branch, which
    is the git branch the clone checks out, rather than the platform default branch which may differ
    and would not exist locally.
    """
    if init_failed or repo.reinitialized:
        return repo.default_branch
    return None


async def bootstrap_local_repository(
    repo_name: str,
    repository: CoreRepository,
    infrahub_branch: str,
    client: InfrahubClient,
    state: DeliveryStatePort,
) -> InfrahubRepository | None:
    """Ensure this worker has a usable local clone and seed the graph for a freshly created repo.

    The repository lock covers the git working-copy mutations.
    Returns None when the repository should be skipped for this cycle: the clone fails, or the
    default-branch import cannot reach the remote or its credentials are invalid. Any other failed
    default-branch import is already logged and recorded on the branch, so the repository is still
    returned and its other branches still synchronize. While the repository has pending pushes, a
    fresh clone records no commit and the seed import is skipped, because the import would remove
    the objects of the pending merges.
    """
    log = get_run_logger()
    pending_import: PendingObjectImport | None = None
    async with lock.registry.get(name=repo_name, namespace="repository"):
        init_failed = False
        try:
            repo = await InfrahubRepository.init(
                id=repository.id,
                name=repository.name.value,
                location=repository.location.value,
                client=client,
                infrahub_branch_name=infrahub_branch,
            )
        except RepositoryError as exc:
            get_logger().error(str(exc))
            init_failed = True

        delivery_pending = False
        if init_failed:
            delivery_pending = repository.id in await state.pending_repository_ids()
            try:
                repo = await InfrahubRepository.new(
                    id=repository.id,
                    name=repository.name.value,
                    location=repository.location.value,
                    client=client,
                    infrahub_branch_name=infrahub_branch,
                    # With the seed import skipped, the graph would record a commit whose objects it lacks.
                    update_commit_value=not delivery_pending,
                )
            except RepositoryError as exc:
                log.info(exc.message)
                return None
        elif repo.reinitialized:
            delivery_pending = repository.id in await state.pending_repository_ids()

        default_import_git_branch = resolve_initial_import_branch(repo, init_failed=init_failed)

        if default_import_git_branch is not None and delivery_pending:
            log.info(
                f"Deferred the import of the default branch {default_import_git_branch} of repository "
                f"{repo.name} until its pending pushes reach the remote"
            )
        elif default_import_git_branch is not None:
            # Pin the commit while the lock is held so the import below reads an immutable
            # worktree even though it is built after the lock is released.
            pending_import = PendingObjectImport(
                infrahub_branch_name=infrahub_branch,
                git_branch_name=default_import_git_branch,
                commit=repo.get_commit_value(branch_name=default_import_git_branch, remote=False),
            )

    if pending_import is not None:
        try:
            await import_branch(
                lock_registry=lock.registry, importer=RepositoryFileImporter(), repo=repo, pending_import=pending_import
            )
        except (RepositoryConnectionError, RepositoryCredentialsError) as exc:
            log.info(exc.message)
            return None

    return repo


def build_cycle_fetch_message(
    location: str,
    repository_id: str,
    repository_name: str,
    repository_kind: str,
    default_branch_id: str,
    trunk_commit: str | None,
    reconciled: Sequence[ReconciledBranch],
) -> messages.RefreshGitFetch:
    """Build the one fetch message of a synchronization cycle: the trunk, then every other branch it advanced.

    The trunk is listed first on every cycle, even when it did not move, so a worker that missed an
    earlier message converges on it again. Without a trunk commit the workers pull the trunk instead.
    """
    trunk = BranchCommitPair(
        infrahub_branch_name=registry.default_branch, infrahub_branch_id=default_branch_id, commit=trunk_commit
    )
    advanced = tuple(
        BranchCommitPair(
            infrahub_branch_name=branch.infrahub_branch_name,
            infrahub_branch_id=branch.infrahub_branch_id,
            commit=branch.commit,
        )
        for branch in reconciled
        if branch.infrahub_branch_name != trunk.infrahub_branch_name
    )
    return messages.RefreshGitFetch(
        meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
        location=location,
        repository_id=repository_id,
        repository_name=repository_name,
        repository_kind=repository_kind,
        infrahub_branch_name=trunk.infrahub_branch_name,
        infrahub_branch_id=trunk.infrahub_branch_id,
        commit=trunk.commit,
        branches=(trunk, *advanced),
    )


async def sync_repository_from_origin(
    repository: CoreRepository,
    repo: InfrahubRepository,
    staging_branch: str | None,
    infrahub_branch: str,
    default_branch_id: str,
    client: InfrahubClient,
    graph_commits: dict[str, str | None] | None = None,
) -> None:
    """Sync the repository from its origin and send the worker pool the commits of the cycle.

    The message goes out before a failed branch is handled, so the failure never keeps the branches
    that advanced from converging on the other workers. No failed branch is raised from here: a
    failed default branch is logged as an error and recorded on the repository's synchronization
    status, and the tagging flow has already linked and failed its own run.
    """
    log = get_run_logger()
    failure: RepositoryBranchesFailedError | None = None
    try:
        outcome = await sync_git_repo_with_origin_and_tag_on_failure(
            client=client,
            repository_id=repository.id,
            repository_name=repository.name.value,
            repository_location=repository.location.value,
            operational_status=repository.operational_status.value,
            staging_branch=staging_branch,
            infrahub_branch=infrahub_branch,
            graph_commits=graph_commits,
        )
    except RepositoryBranchesFailedError as exc:
        outcome = exc.outcome
        failure = exc
    except (RepositoryError, CommitNotFoundError) as exc:
        log.info(exc.message)
        return

    try:
        trunk_commit: str | None = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
    except (ValueError, InvalidGitRepositoryError) as exc:
        log.debug(f"Could not resolve pinned commit for {repository.name.value}, workers will fall back to pull: {exc}")
        trunk_commit = None
    # Pinned SHAs, so the whole pool converges on the same commits even if upstream advances during fan-out.
    message = build_cycle_fetch_message(
        location=repository.location.value,
        repository_id=repository.id,
        repository_name=repository.name.value,
        repository_kind=repository.get_kind(),
        default_branch_id=default_branch_id,
        trunk_commit=trunk_commit,
        reconciled=outcome.reconciled,
    )
    try:
        message_bus = await get_message_bus()
        await message_bus.send(message=message)
    finally:
        # A broadcast that fails must not also hide a failed default branch.
        if failure is not None:
            await report_failed_branches(repo=repo, failure=failure, infrahub_branch=infrahub_branch)


async def report_failed_branches(
    repo: InfrahubRepository, failure: RepositoryBranchesFailedError, infrahub_branch: str
) -> None:
    """Log the branches a synchronization failed, and record a failed import of the default branch on the repository.

    A failed default branch is loud but never raised, since a raise would stop every repository after
    this one. A failed rewrite record is logged like any other failure of the default branch, but it
    leaves the synchronization status alone, because the objects of the branch were still imported.
    """
    log = get_run_logger()
    default_branch_failures = failure.outcome.default_branch_failures
    for failed in default_branch_failures:
        log.error(
            f"Unable to synchronize the default branch {repo.default_branch} of repository "
            f"{repo.name} at step {failed.step.value}: {failed.reason}"
        )
    if failure.outcome.default_branch_import_failures:
        await repo.record_import_failure(infrahub_branch_name=infrahub_branch)
    if len(default_branch_failures) < len(failure.outcome.failed):
        log.info(failure.message)


async def sync_remote_repository(
    repo_name: str,
    repository_data: RepositoryData,
    branches: dict[str, BranchData],
    client: InfrahubClient,
    state: DeliveryStatePort,
) -> None:
    """Synchronize one repository with its origin, cloning it on this worker first when needed."""
    repository: CoreRepository = repository_data.repository

    default_internal_status = repository_data.branch_info[registry.default_branch].internal_status
    staging_branch = None
    if default_internal_status != RepositoryInternalStatus.ACTIVE.value:
        staging_branch = repository_data.get_staging_branch()

    infrahub_branch = staging_branch or registry.default_branch

    repo = await bootstrap_local_repository(
        repo_name=repo_name,
        repository=repository,
        infrahub_branch=infrahub_branch,
        client=client,
        state=state,
    )
    if repo is None:
        return

    await sync_repository_from_origin(
        repository=repository,
        repo=repo,
        staging_branch=staging_branch,
        infrahub_branch=infrahub_branch,
        default_branch_id=branches[registry.default_branch].id,
        client=client,
        graph_commits=select_writable_branch_commits(branch_commits=repository_data.branches, branches=branches),
    )


@flow(name="git_repositories_sync", flow_run_name="Sync Git Repositories")
async def sync_remote_repositories() -> None:
    db = await get_database()

    client = get_client()
    log = get_run_logger()

    branches = await client.branch.all()
    async with db.start_session() as dbs:
        repositories = await get_repositories_commit_per_branch(db=dbs, kind=InfrahubKind.REPOSITORY)
        state = await build_intent_store(db=dbs, lock_registry=lock.registry)

        for repo_name, repository_data in repositories.items():
            try:
                await sync_remote_repository(
                    repo_name=repo_name, repository_data=repository_data, branches=branches, client=client, state=state
                )
            # One repository that fails must not stop the cycle for the repositories after it.
            except Exception:
                log.exception(f"Unable to synchronize repository {repo_name}, continuing with the other repositories")


@task(
    name="git-branch-create",
    task_run_name="Create branch '{branch}' in repository {repository_name}",
    cache_policy=NONE,
)
async def git_branch_create(
    client: InfrahubClient,
    branch: str,
    branch_id: str,
    repository_id: str,
    repository_name: str,
    repository_location: str,
    message_bus: InfrahubMessageBus,
) -> None:
    log = get_run_logger()
    # Read on the default branch: the branch being created is not guaranteed to be visible to this
    # worker's client yet.
    try:
        repo = await InfrahubRepository.init(
            id=repository_id,
            name=repository_name,
            location=repository_location,
            client=client,
            infrahub_branch_name=registry.default_branch,
        )
    except RepositoryError as exc:
        log.warning(f"Skipping branch creation for repository '{repository_name}' - {exc.message}")
        return

    async with lock.registry.get(name=repository_name, namespace="repository"):
        created = await repo.create_branch_in_git(branch_name=branch, branch_id=branch_id, push_origin=True)

        try:
            pinned_commit: str | None = repo.get_commit_value(branch_name=branch, remote=False)
        except (ValueError, InvalidGitRepositoryError):
            pinned_commit = None
        # Unwritten, the branch reads its origin branch's commit, and a sync would classify against that.
        if created and pinned_commit is not None:
            try:
                await repo.update_commit_value(branch_name=branch, commit=pinned_commit)
            except SdkError as exc:
                # The next sync records a commit the graph lacks, but nothing resends the broadcast below.
                log.warning(
                    f"Unable to record commit {pinned_commit} of the new branch '{branch}' for repository "
                    f"'{repository_name}', the next synchronization records it - {exc.message}"
                )
        # New branch has been pushed remotely, tell workers to fetch it and check out the SHA it
        # was created at so the pool converges even if upstream advances during fan-out.
        message = messages.RefreshGitFetch(
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
            location=repo.get_location(),
            repository_id=str(repo.id),
            repository_name=repo.name,
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=branch,
            infrahub_branch_id=branch_id,
            commit=pinned_commit,
        )
        await message_bus.send(message=message)
        log.debug("Sent message to all workers to fetch the latest version of the repository (RefreshGitFetch)")


@task(
    name="git-branch-delete",
    task_run_name="Delete branch '{branch}' in repository {repository_name}",
    cache_policy=NONE,
)
async def git_branch_delete(
    client: InfrahubClient,
    branch: str,
    repository_id: str,
    repository_name: str,
    repository_location: str,
) -> None:
    log = get_run_logger()
    await add_branch_tag(branch_name=branch)
    # Read on the default branch: this fan-out runs after the Infrahub branch has been deleted, so
    # reading the node on it would raise.
    try:
        repo = await InfrahubRepository.init(
            id=repository_id,
            name=repository_name,
            location=repository_location,
            client=client,
            infrahub_branch_name=registry.default_branch,
        )
    except RepositoryError as exc:
        log.warning(f"Skipping branch deletion for repository '{repository_name}' - {exc.message}")
        return

    async with lock.registry.get(name=repository_name, namespace="repository"):
        if not repo.origin_has_branch(branch):
            return

        try:
            await repo.delete_remote_branch(branch_name=branch)
        except Exception as exc:
            log.exception(f"Failed to delete Git branch '{branch}' from repository '{repository_name}' - {str(exc)}")
            return

        message_bus = await get_message_bus()
        message = messages.RefreshGitRepositoryBranchDeleted(
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
            repository_id=str(repo.id),
            repository_name=repo.name,
            repository_kind=InfrahubKind.REPOSITORY,
            branch_name=branch,
        )
        await message_bus.send(message=message)
        log.info("Sent message to all workers to delete local branch")


@flow(name="artifact-definition-generate", flow_run_name="Generate all artifacts")
async def generate_artifact_definition(branch: str, context: InfrahubContext) -> None:
    await add_branch_tag(branch_name=branch)

    client = get_client()
    client.request_context = context.to_request_context()
    artifact_definitions = await client.all(kind=CoreArtifactDefinition, branch=branch, include=["id"])

    for artifact_definition in artifact_definitions:
        model = RequestArtifactDefinitionGenerate(
            branch=branch,
            artifact_definition_id=artifact_definition.id,
            artifact_definition_name=artifact_definition.name.value,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"model": model}
        )


@flow(name="artifact-generate", flow_run_name="Generate artifact {model.artifact_name}")
async def generate_artifact(model: RequestArtifactGenerate) -> None:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])
    log = get_run_logger()
    client = get_client()
    client.request_context = model.context.to_request_context()
    repo = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        infrahub_branch_name=model.branch_name,
        commit=model.commit,
    )

    artifact, artifact_created = await define_artifact(model=model)

    try:
        result = await repo.render_artifact(artifact=artifact, artifact_created=artifact_created, message=model)
        log.debug(
            f"Generated artifact | changed: {result.changed} | {result.checksum} | {result.storage_id}",
        )
    except Exception:
        log.exception("Failed to generate artifact")
        artifact.status.value = "Error"
        await artifact.save()
        raise


@flow(
    name="request_artifact_definitions_generate",
    flow_run_name="Trigger Generation of Artifacts for {model.artifact_definition_name}",
)
async def generate_request_artifact_definition(
    model: RequestArtifactDefinitionGenerate, context: InfrahubContext
) -> None:
    await add_tags(branches=[model.branch])

    client = get_client()
    client.request_context = context.to_request_context()

    # Needs to be fetched before fetching group members otherwise `object` relationship would override
    # existing node in client store without the `name` attribute due to #521
    existing_artifacts = await client.filters(
        kind=CoreArtifact,
        definition__ids=[model.artifact_definition_id],
        include=["object"],
        branch=model.branch,
    )

    artifact_definition = await client.get(
        kind=CoreArtifactDefinition, id=model.artifact_definition_id, branch=model.branch
    )

    group = await fetch_artifact_definition_targets(client=client, branch=model.branch, definition=artifact_definition)

    current_members = [member.id for member in group.members.peers]

    artifacts_by_member = {}
    stale_artifacts = []
    for artifact in existing_artifacts:
        if artifact.object.id in current_members:
            artifacts_by_member[artifact.object.peer.id] = artifact.id
        else:
            stale_artifacts.append(artifact)

    await artifact_definition.transformation.fetch()
    transformation_repository = artifact_definition.transformation.peer.repository

    await transformation_repository.fetch()

    transform = artifact_definition.transformation.peer
    await transform.query.fetch()
    query = transform.query.peer
    repository = transformation_repository.peer
    branch = await client.branch.get(branch_name=model.branch)
    if branch.sync_with_git:
        repository = await client.get(kind=CoreGenericRepository, id=repository.id, branch=model.branch, fragment=True)
    transform_location = ""

    convert_query_response = False
    if transform.typename == InfrahubKind.TRANSFORMJINJA2:
        transform_location = transform.template_path.value
    elif transform.typename == InfrahubKind.TRANSFORMPYTHON:
        transform_location = f"{transform.file_path.value}::{transform.class_name.value}"
        convert_query_response = transform.convert_query_response.value

    batch = await client.create_batch()
    for relationship in group.members.peers:
        member = relationship.peer
        artifact_id = artifacts_by_member.get(member.id)
        if not model.selects_member(member_id=member.id, artifact_id=artifact_id):
            continue

        request_artifact_generate_model = RequestArtifactGenerate(
            artifact_name=artifact_definition.artifact_name.value,
            artifact_id=artifact_id,
            artifact_definition=model.artifact_definition_id,
            artifact_definition_name=model.artifact_definition_name,
            commit=repository.commit.value,
            content_type=artifact_definition.content_type.value,
            transform_type=str(transform.typename),
            transform_location=transform_location,
            repository_id=repository.id,
            repository_name=repository.name.value,
            repository_kind=repository.get_kind(),
            branch_name=model.branch,
            query=query.name.value,
            query_id=query.id,
            variables=await member.extract(params=artifact_definition.parameters.value),
            target_id=member.id,
            target_name=member.display_label,
            target_kind=member.get_kind(),
            timeout=transform.timeout.value,
            convert_query_response=convert_query_response,
            context=context,
            check_stored_file=bool(model.limit),
        )

        batch.add(
            task=get_workflow().submit_workflow,
            workflow=REQUEST_ARTIFACT_GENERATE,
            context=context,
            parameters={"model": request_artifact_generate_model},
        )

    async for _, _ in batch.execute():
        pass

    # A full pass over the definition also cleans up artifacts whose target is no
    # longer a member of the target group; a limited run only regenerates the
    # requested artifacts and must not delete anything else. The cleanup runs
    # after the regeneration is dispatched and tolerates individual failures:
    # a stale artifact that cannot be deleted must not block the regeneration
    # of current members.
    if model.evaluates_every_member:
        log = get_run_logger()
        for artifact in stale_artifacts:
            try:
                await artifact.delete()
                log.info(
                    f"Deleted artifact {artifact.id} ({artifact.name.value}) on branch {model.branch}: "
                    f"its target {artifact.object.id} is no longer a member of the definition's targets"
                )
            except Exception:
                log.warning(
                    f"Failed to delete stale artifact {artifact.id} ({artifact.name.value}) on branch {model.branch}",
                    exc_info=True,
                )


@flow(name="git-repository-pull-read-only", flow_run_name="Pull latest commit on {model.repository_name}")
async def pull_read_only(model: GitRepositoryPullReadOnly) -> None:
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])
    log = get_run_logger()

    if not model.ref and not model.commit:
        log.warning("No commit or ref in GitRepositoryPullReadOnly message")
        return
    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        init_failed = False
        try:
            repo = await InfrahubReadOnlyRepository.init(
                id=model.repository_id,
                name=model.repository_name,
                location=model.location,
                client=get_client(),
                ref=model.ref,
                infrahub_branch_name=model.infrahub_branch_name,
            )
        except RepositoryError:
            init_failed = True

        if init_failed:
            repo = await InfrahubReadOnlyRepository.new(
                id=model.repository_id,
                name=model.repository_name,
                location=model.location,
                client=get_client(),
                ref=model.ref,
                infrahub_branch_name=model.infrahub_branch_name,
            )

        # Resolve the ref to a concrete commit once so the sync and the broadcast share the same
        # SHA. model.commit may be None for a ref-only pull, in which case broadcasting it would
        # leave workers to re-resolve the ref independently and diverge.
        pinned_commit = model.commit
        if pinned_commit is None and repo.ref:
            pinned_commit = repo.get_commit_value(branch_name=repo.ref, remote=True)

        await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name, commit=pinned_commit)  # type: ignore[call-overload]
        await repo.sync_from_remote(commit=pinned_commit)

        # Tell workers to fetch and check out the resolved commit to stay in sync
        message = messages.RefreshGitFetch(
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
            location=model.location,
            repository_id=model.repository_id,
            repository_name=model.repository_name,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            infrahub_branch_name=model.infrahub_branch_name,
            infrahub_branch_id=model.infrahub_branch_id,
            commit=pinned_commit,
        )
        message_bus = await get_message_bus()
        await message_bus.send(message=message)


async def _read_destination_commit(
    client: InfrahubClient, repo: InfrahubRepository, model: GitRepositoryMerge
) -> str | None:
    """Return the commit the graph records for the destination now, which an earlier merge can move after the dispatch.

    Raises:
        RepositoryError: When the API cannot answer.

    """
    try:
        repository = await client.get(kind=CoreRepository, id=model.repository_id, branch=model.destination_branch)
    except SdkError as exc:
        raise RepositoryError(
            identifier=model.repository_name,
            message=repo.unfinished_merge_message(
                source_branch=model.source_branch,
                dest_branch=model.destination_branch,
                reason=(
                    f"Infrahub cannot read the commit it records for {model.destination_branch} "
                    f"({(exc.message or type(exc).__name__).rstrip('.')})."
                ),
            ),
        ) from exc
    return readable_commit(repository.commit.value)


@flow(
    name="git-repository-merge",
    flow_run_name="Merge {model.source_branch} > {model.destination_branch} in git repository",
)
async def merge_git_repository(model: GitRepositoryMerge) -> None:
    log = get_run_logger()
    await add_tags(branches=[model.source_branch, model.destination_branch], nodes=[model.repository_id])

    client = get_client()

    # A read-only repository merges by copying two attributes between branches and never touches a
    # local clone, so it must not build a read-write repository object: its node is not a
    # CoreRepository, and resolving one would raise.
    if model.repository_kind == InfrahubKind.READONLYREPOSITORY:
        repo_destination = await client.get(
            kind=CoreReadOnlyRepository, id=model.repository_id, branch=model.destination_branch
        )
        source_ref, source_commit = model.source_ref, model.source_commit
        # Only a merge that an older version queued carries neither value.
        if source_ref is None and source_commit is None:
            repo_source = await client.get(
                kind=CoreReadOnlyRepository, id=model.repository_id, branch=model.source_branch
            )
            source_ref, source_commit = repo_source.ref.value, repo_source.commit.value

        if repo_destination.ref.value != source_ref or repo_destination.commit.value != source_commit:
            log.info(f"Merging {model.repository_kind}")

            repo_destination.ref.value = source_ref
            repo_destination.commit.value = source_commit
            await repo_destination.save()

            log.info(f"Finished merging {model.repository_kind}")
        return

    # The merge lands on the destination branch, and the staging decision below comes from the model
    # rather than from the object, so the destination is the branch to resolve on.
    repo = await InfrahubRepository.init(
        id=model.repository_id,
        name=model.repository_name,
        client=client,
        infrahub_branch_name=model.destination_branch,
    )

    if model.internal_status == RepositoryInternalStatus.STAGING.value:
        log.info(f"Merging {model.repository_kind}")
        repo_source = await client.get(kind=CoreGenericRepository, id=model.repository_id, branch=model.source_branch)
        repo_main = await client.get(kind=CoreGenericRepository, id=model.repository_id)
        repo_main.internal_status.value = RepositoryInternalStatus.ACTIVE.value
        repo_main.sync_status.value = repo_source.sync_status.value

        commit = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
        repo_main.commit.value = commit

        await repo_main.save()
        log.info(f"Finished merging {model.repository_kind}")

    else:
        async with lock.registry.get(name=model.repository_name, namespace="repository"):
            await repo.prepare_branches_for_merge(
                source_branch=model.source_branch,
                dest_branch=model.destination_branch,
                source_commit=model.source_commit,
                destination_commit=await _read_destination_commit(client=client, repo=repo, model=model),
            )
            await repo.merge(source_branch=model.source_branch, dest_branch=model.destination_branch)
            if repo.location:
                try:
                    pinned_commit: str | None = repo.get_commit_value(
                        branch_name=model.destination_branch, remote=False
                    )
                except (ValueError, InvalidGitRepositoryError):
                    pinned_commit = None
                # Destination branch has changed and pushed remotely, tell workers to re-fetch and
                # check out the merge commit so the pool converges even if upstream advances meanwhile.
                message = messages.RefreshGitFetch(
                    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                    location=repo.location,
                    repository_id=str(repo.id),
                    repository_name=repo.name,
                    repository_kind=InfrahubKind.REPOSITORY,
                    infrahub_branch_name=model.destination_branch,
                    infrahub_branch_id=model.destination_branch_id,
                    commit=pinned_commit,
                )
                message_bus = await get_message_bus()
                await message_bus.send(message=message)


@flow(name="git-repository-import-object", flow_run_name="Import objects from git repository")
async def import_objects_from_git_repository(model: GitRepositoryImportObjects) -> None:
    await add_branch_tag(model.infrahub_branch_name)

    client = get_client()

    repo = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        infrahub_branch_name=model.infrahub_branch_name,
        commit=model.commit,
    )
    plan = await repo.build_import_plan(infrahub_branch_name=model.infrahub_branch_name, commit=model.commit)
    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        await repo.apply_import_plan(plan)


@flow(
    name="git-read-only-repository-import-last-commit", flow_run_name="Import last commit from read only git repository"
)
async def import_read_only_repository_last_commit(model: GitReadOnlyRepositoryImportCommit) -> None:
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])

    if not model.repository_kind == InfrahubKind.READONLYREPOSITORY:
        raise RepositoryError(identifier=model.repository_name, message="Repository is not a read only repository")

    client = get_client()

    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        repo = await InfrahubReadOnlyRepository.init(
            id=model.repository_id,
            name=model.repository_name,
            client=client,
            infrahub_branch_name=model.infrahub_branch_name,
            ref=model.ref,
        )
        await repo.update_latest_commit(
            tracked_targets=SdkTrackedTargetReader(client=client),
            recorder=HistoryRewriteRecorder(store=SdkRepositoryRecordStore(client=client)),
            # Two mutations submit this flow, and only the submitter knows whether it re-pointed the repository.
            target_changed=model.target_changed,
        )


@flow(
    name="git-repository-diff-names-only",
    flow_run_name="Collecting modifications between commits {model.first_commit} and {model.second_commit}",
    persist_result=True,
)
async def git_repository_diff_names_only(model: GitDiffNamesOnly) -> GitDiffNamesOnlyResponse:
    repo = await get_initialized_repo(
        client=get_client(),
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        infrahub_branch_name=model.infrahub_branch_name,
    )
    files_changed: list[str] = []
    files_removed: list[str] = []

    if model.second_commit:
        files_changed, files_added, files_removed = await repo.calculate_diff_between_commits(
            first_commit=model.first_commit, second_commit=model.second_commit
        )
    else:
        files_added = await repo.list_all_files(commit=model.first_commit)

    return GitDiffNamesOnlyResponse(files_added=files_added, files_changed=files_changed, files_removed=files_removed)


@flow(
    name="git-repository-user-checks-definition-trigger",
    flow_run_name="Trigger user defined checks for repository {model.repository_name}",
)
async def trigger_repository_user_checks_definitions(model: UserCheckDefinitionData, context: InfrahubContext) -> None:
    await add_tags(branches=[model.branch_name], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    definition = await client.get(kind=CoreCheckDefinition, id=model.check_definition_id, branch=model.branch_name)
    proposed_change = await client.get(kind=CoreProposedChange, id=model.proposed_change)
    validator_execution_id = str(UUIDT())
    check_execution_ids: list[str] = []
    await proposed_change.validations.fetch()

    previous_validator: CoreUserValidator | None = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer

        if (
            existing_validator.typename == InfrahubKind.USERVALIDATOR
            and existing_validator.repository.id == model.repository_id
            and existing_validator.check_definition.id == model.check_definition_id
        ):
            previous_validator = existing_validator
            get_logger().info("Found the same validator", validator=previous_validator)

    validator = await start_validator(
        client=client,
        validator=previous_validator,
        validator_type=CoreUserValidator,
        proposed_change=model.proposed_change,
        data={
            "label": f"Check: {definition.name.value}",
            "repository": model.repository_id,
            "check_definition": model.check_definition_id,
        },
        context=context,
    )

    if definition.targets.id:
        # Check against a group of targets
        group = await fetch_check_definition_targets(client=client, branch=model.branch_name, definition=definition)
        check_models = []
        for relationship in group.members.peers:
            member = relationship.peer

            check_execution_id = str(UUIDT())
            check_execution_ids.append(check_execution_id)
            check_model = UserCheckData(
                name=member.display_label,
                validator_id=validator.id,
                validator_execution_id=validator_execution_id,
                check_execution_id=check_execution_id,
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                repository_kind=model.repository_kind,
                commit=model.commit,
                file_path=model.file_path,
                class_name=model.class_name,
                branch_name=model.branch_name,
                check_definition_id=model.check_definition_id,
                proposed_change=model.proposed_change,
                variables=await member.extract(params=definition.parameters.value),
                branch_diff=model.branch_diff,
                timeout=definition.timeout.value,
            )
            check_models.append(check_model)
    else:
        check_execution_id = str(UUIDT())
        check_execution_ids.append(check_execution_id)
        check_models = [
            UserCheckData(
                name=definition.name.value,
                validator_id=validator.id,
                validator_execution_id=validator_execution_id,
                check_execution_id=check_execution_id,
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                repository_kind=model.repository_kind,
                commit=model.commit,
                file_path=model.file_path,
                class_name=model.class_name,
                branch_name=model.branch_name,
                check_definition_id=model.check_definition_id,
                proposed_change=model.proposed_change,
                branch_diff=model.branch_diff,
                timeout=definition.timeout.value,
            )
        ]

    checks_in_execution = ",".join(check_execution_ids)
    log.info(f"Checks in execution {checks_in_execution}")

    workflow = get_workflow()
    checks_coroutines = [
        workflow.execute_workflow(
            workflow=GIT_REPOSITORY_USER_CHECK_RUN,
            context=context,
            parameters={"model": model},
            expected_return=ValidatorConclusion,
        )
        for model in check_models
    ]

    event_service = await get_event_service()
    await run_checks_and_update_validator(
        event_service=event_service,
        checks=checks_coroutines,
        validator=validator,
        context=context,
        proposed_change_id=model.proposed_change,
    )


@flow(
    name="git-repository-trigger-user-checks",
    flow_run_name="Evaluating user-defined checks on repository {model.repository_name}",
)
async def trigger_user_checks(model: TriggerRepositoryUserChecks, context: InfrahubContext) -> None:
    """Request to start validation checks on a specific repository for User-defined checks."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    repository = await client.get(
        kind=CoreGenericRepository, id=model.repository_id, branch=model.source_branch, fragment=True
    )
    await repository.checks.fetch()

    workflow = get_workflow()
    for relationship in repository.checks.peers:
        log.info("Adding check for user defined check")
        check_definition = relationship.peer
        user_check_definition_model = UserCheckDefinitionData(
            check_definition_id=check_definition.id,
            repository_id=repository.id,
            repository_name=repository.name.value,
            repository_kind=model.repository_kind,
            commit=repository.commit.value,
            file_path=check_definition.file_path.value,
            class_name=check_definition.class_name.value,
            branch_name=model.source_branch,
            proposed_change=model.proposed_change,
            branch_diff=model.branch_diff,
        )
        await workflow.submit_workflow(
            workflow=GIT_REPOSITORY_USER_CHECKS_DEFINITIONS_TRIGGER,
            context=context,
            parameters={"model": user_check_definition_model},
        )


@flow(
    name="git-repository-trigger-internal-checks",
    flow_run_name="Running repository checks for repository {model.repository}",
)
async def trigger_internal_checks(model: TriggerRepositoryInternalChecks, context: InfrahubContext) -> None:
    """Request to start validation checks on a specific repository."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    repository = await client.get(kind=CoreGenericRepository, id=model.repository, branch=model.source_branch)
    proposed_change = await client.get(kind=CoreProposedChange, id=model.proposed_change)

    validator_execution_id = str(UUIDT())
    check_execution_ids: list[str] = []
    await proposed_change.validations.fetch()
    await repository.checks.fetch()

    validator_name = f"Repository Validator: {repository.name.value}"
    previous_validator: CoreRepositoryValidator | None = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer

        if (
            existing_validator.typename == InfrahubKind.REPOSITORYVALIDATOR
            and existing_validator.repository.id == model.repository
            and existing_validator.label.value == validator_name
        ):
            previous_validator = existing_validator

    validator = await start_validator(
        client=client,
        validator=previous_validator,
        validator_type=CoreRepositoryValidator,
        proposed_change=model.proposed_change,
        data={"label": validator_name, "repository": model.repository},
        context=context,
    )

    check_execution_id = str(UUIDT())
    check_execution_ids.append(check_execution_id)
    log.info("Adding check for import status")

    check_import_status_model = CheckRepositoryImportStatus(
        validator_id=validator.id,
        validator_execution_id=validator_execution_id,
        check_execution_id=check_execution_id,
        proposed_change=model.proposed_change,
        repository_id=model.repository,
        repository_name=repository.name.value,
        repository_internal_status=repository.internal_status.value,
        source_branch=model.source_branch,
    )
    check_coroutines = [
        get_workflow().execute_workflow(
            workflow=GIT_REPOSITORY_IMPORT_STATUS_CHECKS_RUN,
            context=context,
            parameters={"model": check_import_status_model},
            expected_return=ValidatorConclusion,
        )
    ]

    if model.check_merge_conflicts:
        check_execution_id = str(UUIDT())
        check_execution_ids.append(check_execution_id)
        log.info("Adding check for merge conflict")

        check_merge_conflict_model = CheckRepositoryMergeConflicts(
            validator_id=validator.id,
            validator_execution_id=validator_execution_id,
            check_execution_id=check_execution_id,
            proposed_change=model.proposed_change,
            repository_id=model.repository,
            repository_name=repository.name.value,
            source_branch=model.source_branch,
            target_branch=model.target_branch,
        )
        check_coroutines.append(
            get_workflow().execute_workflow(
                workflow=GIT_REPOSITORY_MERGE_CONFLICTS_CHECKS_RUN,
                context=context,
                parameters={"model": check_merge_conflict_model},
                expected_return=ValidatorConclusion,
            )
        )
    else:
        await validator.checks.fetch()
        for relationship in validator.checks.peers:
            check_peer = relationship.peer
            if check_peer.typename == InfrahubKind.FILECHECK and check_peer.kind.value == MERGE_CONFLICT_CHECK_KIND:
                log.info(f"Removing merge conflict check '{check_peer.name.value}', which no longer applies")
                await check_peer.delete()

    checks_in_execution = ",".join(check_execution_ids)
    log.info(f"Checks in execution {checks_in_execution}")

    event_service = await get_event_service()
    await run_checks_and_update_validator(
        event_service=event_service,
        checks=check_coroutines,
        validator=validator,
        context=context,
        proposed_change_id=model.proposed_change,
    )


@flow(
    name="git-repository-check-import-status",
    flow_run_name="Check the import status of {model.repository_name} on {model.source_branch}",
)
async def run_check_repository_import_status(model: CheckRepositoryImportStatus) -> ValidatorConclusion:
    """Runs a check to see if the last import of the objects of a repository on a branch failed."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()
    database = await get_database()

    validator = await client.get(kind=CoreRepositoryValidator, id=model.validator_id)
    await validator.checks.fetch()

    async with database.start_session(read_only=True) as db:
        source_branch = await registry.get_branch(db=db, branch=model.source_branch)
        sync_status = await RepositoryBranchSyncStatusReader(db=db).get_status_written_on_branch(
            repository_id=model.repository_id, branch=source_branch
        )

    outcome = evaluate_import_status(
        sync_status=sync_status,
        internal_status=RepositoryInternalStatus(model.repository_internal_status),
        repository_name=model.repository_name,
        branch_name=model.source_branch,
    )
    if outcome.conclusion is ValidatorConclusion.FAILURE:
        log.warning(outcome.message)
    else:
        log.info(f"No import error reported for {model.repository_name} on {model.source_branch}")

    existing_check = None
    for relationship in validator.checks.peers:
        check_peer = relationship.peer
        if check_peer.typename == InfrahubKind.STANDARDCHECK and check_peer.kind.value == IMPORT_STATUS_CHECK_KIND:
            existing_check = check_peer

    if existing_check:
        existing_check.created_at.value = Timestamp().to_string()
        existing_check.message.value = outcome.message
        existing_check.conclusion.value = outcome.conclusion.value
        existing_check.severity.value = outcome.severity.value
        await existing_check.save()
    else:
        check = await client.create(
            kind=CoreStandardCheck,
            data={
                "name": IMPORT_STATUS_CHECK_NAME,
                "origin": model.repository_id,
                "kind": IMPORT_STATUS_CHECK_KIND,
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "message": outcome.message,
                "conclusion": outcome.conclusion.value,
                "severity": outcome.severity.value,
            },
        )
        await check.save()

    return outcome.conclusion


@flow(
    name="git-repository-check-merge-conflict",
    flow_run_name="Check for merge conflicts between {model.source_branch} and {model.target_branch}",
)
async def run_check_merge_conflicts(model: CheckRepositoryMergeConflicts) -> ValidatorConclusion:
    """Runs a check to see if there are merge conflicts between two branches."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    client = get_client()

    success_condition = "-"
    validator = await client.get(kind=CoreRepositoryValidator, id=model.validator_id)
    await validator.checks.fetch()

    repo = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=InfrahubKind.REPOSITORY,
        # Merge-conflict checks only run for active read-write repositories, so the node is readable
        # on the proposed change's source branch.
        infrahub_branch_name=model.source_branch,
    )
    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        conflicts = await repo.get_conflicts(source_branch=model.source_branch, dest_branch=model.target_branch)

    existing_checks = {}
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if existing_check.typename == InfrahubKind.FILECHECK and existing_check.kind.value == MERGE_CONFLICT_CHECK_KIND:
            check_key = ""
            if existing_check.files.value:
                check_key = "".join(existing_check.files.value)
            check_key = f"-{check_key}"
            existing_checks[check_key] = existing_check

    if conflicts:
        validator_conclusion = ValidatorConclusion.FAILURE
        for conflict in conflicts:
            conflict_key = f"-{conflict}"
            if conflict_key in existing_checks:
                existing_checks[conflict_key].created_at.value = Timestamp().to_string()
                await existing_checks[conflict_key].save()
                existing_checks.pop(conflict_key)
            else:
                check = await client.create(
                    kind=CoreFileCheck,
                    data={
                        "name": conflict,
                        "origin": "ConflictCheck",
                        "kind": MERGE_CONFLICT_CHECK_KIND,
                        "validator": model.validator_id,
                        "created_at": Timestamp().to_string(),
                        "files": [conflict],
                        "conclusion": "failure",
                        "severity": "critical",
                    },
                )
                await check.save()

    elif success_condition in existing_checks:
        validator_conclusion = ValidatorConclusion.SUCCESS
        existing_checks[success_condition].created_at.value = Timestamp().to_string()
        await existing_checks[success_condition].save()
        existing_checks.pop(success_condition)

    else:
        validator_conclusion = ValidatorConclusion.SUCCESS
        check = await client.create(
            kind=CoreFileCheck,
            data={
                "name": "Merge Conflict Check",
                "origin": "ConflictCheck",
                "kind": MERGE_CONFLICT_CHECK_KIND,
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "conclusion": validator_conclusion.value,
                "severity": "info",
            },
        )
        await check.save()

    database = await get_database()
    for check in existing_checks.values():
        async with database.start_transaction() as dbt:
            await NodeManager.delete(db=dbt, nodes=[check])

    return validator_conclusion


@flow(name="git-repository-run-user-check", flow_run_name="Execute user defined Check '{model.name}'")
async def run_user_check(model: UserCheckData) -> ValidatorConclusion:
    await add_tags(branches=[model.branch_name], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()

    validator = await client.get(kind=CoreUserValidator, id=model.validator_id)
    await validator.checks.fetch()

    repo = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        infrahub_branch_name=model.branch_name,
        commit=model.commit,
    )
    conclusion = ValidatorConclusion.FAILURE
    severity = "critical"
    try:
        check_run = await repo.execute_python_check.with_options(timeout_seconds=model.timeout)(
            branch_name=model.branch_name,
            location=model.file_path,
            class_name=model.class_name,
            client=client,
            commit=model.commit,
            params=model.variables,
        )  # type: ignore[call-overload]
        if check_run.passed:
            conclusion = ValidatorConclusion.SUCCESS
            severity = "info"
            log.info("The check passed")
        else:
            log.warning("The check reported failures")
            for entry in check_run.logs:
                log.warning(format_check_log_entry(entry))
        log_entries = check_run.log_entries
    except CheckError as exc:
        log.warning("The check failed to run")
        log.error(exc.message)
        log_entries = f"FATAL Error/n:{exc.message}"

    check = None
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if (
            existing_check.typename == InfrahubKind.STANDARDCHECK
            and existing_check.kind.value == "CheckDefinition"
            and existing_check.name.value == model.name
        ):
            check = existing_check

    if check:
        check.created_at.value = Timestamp().to_string()
        check.message.value = log_entries
        check.conclusion.value = conclusion.value
        check.severity.value = severity
        await check.save()
    else:
        check = await client.create(
            kind=CoreStandardCheck,
            data={
                "name": model.name,
                "origin": model.repository_id,
                "kind": "CheckDefinition",
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "message": log_entries,
                "conclusion": conclusion.value,
                "severity": severity,
            },
        )
        await check.save()

    return conclusion

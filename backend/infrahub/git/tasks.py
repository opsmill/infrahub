from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactDefinition,
    CoreCheckDefinition,
    CoreRepository,
    CoreRepositoryValidator,
    CoreUserValidator,
)
from infrahub_sdk.uuidt import UUIDT
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.context import InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus, ValidatorConclusion
from infrahub.core.registry import registry
from infrahub.exceptions import CheckError, RepositoryError
from infrahub.message_bus import Meta, messages
from infrahub.services import InfrahubServices
from infrahub.validators.tasks import start_validator
from infrahub.worker import WORKER_IDENTITY

from ..core.manager import NodeManager
from ..core.timestamp import Timestamp
from ..core.validators.checks_runner import run_checks_and_update_validator
from ..log import get_log_data
from ..tasks.artifact import define_artifact
from ..workflows.catalogue import (
    GIT_REPOSITORY_MERGE_CONFLICTS_CHECKS_RUN,
    GIT_REPOSITORY_USER_CHECK_RUN,
    GIT_REPOSITORY_USER_CHECKS_DEFINITIONS_TRIGGER,
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_ARTIFACT_GENERATE,
)
from ..workflows.utils import add_branch_tag, add_tags
from .models import (
    CheckRepositoryMergeConflicts,
    GitDiffNamesOnly,
    GitDiffNamesOnlyResponse,
    GitRepositoryAdd,
    GitRepositoryAddReadOnly,
    GitRepositoryImportObjects,
    GitRepositoryMerge,
    GitRepositoryPullReadOnly,
    RequestArtifactDefinitionGenerate,
    RequestArtifactGenerate,
    TriggerRepositoryInternalChecks,
    TriggerRepositoryUserChecks,
    UserCheckData,
    UserCheckDefinitionData,
)
from .repository import InfrahubReadOnlyRepository, InfrahubRepository, get_initialized_repo


@flow(
    name="git-repository-add-read-write",
    flow_run_name="Adding repository {model.repository_name} in branch {model.infrahub_branch_name}",
)
async def add_git_repository(model: GitRepositoryAdd, service: InfrahubServices) -> None:
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])

    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        repo = await InfrahubRepository.new(
            id=model.repository_id,
            name=model.repository_name,
            location=model.location,
            client=service.client,
            infrahub_branch_name=model.infrahub_branch_name,
            internal_status=model.internal_status,
            default_branch_name=model.default_branch_name,
            service=service,
        )
        await repo.import_objects_from_files(  # type: ignore[call-overload]
            infrahub_branch_name=model.infrahub_branch_name, git_branch_name=model.default_branch_name
        )
        if model.internal_status == RepositoryInternalStatus.ACTIVE.value:
            await repo.sync()

            # Notify other workers they need to clone the repository
            notification = messages.RefreshGitFetch(
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                location=model.location,
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=model.infrahub_branch_name,
                infrahub_branch_id=model.infrahub_branch_id,
            )
            await service.message_bus.send(message=notification)


@flow(
    name="git-repository-add-read-only",
    flow_run_name="Adding read only repository {model.repository_name} in branch {model.infrahub_branch_name}",
)
async def add_git_repository_read_only(model: GitRepositoryAddReadOnly, service: InfrahubServices) -> None:
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])

    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        repo = await InfrahubReadOnlyRepository.new(
            id=model.repository_id,
            name=model.repository_name,
            location=model.location,
            client=service.client,
            ref=model.ref,
            infrahub_branch_name=model.infrahub_branch_name,
            service=service,
        )
        await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name)  # type: ignore[call-overload]
        if model.internal_status == RepositoryInternalStatus.ACTIVE.value:
            await repo.sync_from_remote()

            # Notify other workers they need to clone the repository
            notification = messages.RefreshGitFetch(
                meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                location=model.location,
                repository_id=model.repository_id,
                repository_name=model.repository_name,
                repository_kind=InfrahubKind.REPOSITORY,
                infrahub_branch_name=model.infrahub_branch_name,
                infrahub_branch_id=model.infrahub_branch_id,
            )
            await service.message_bus.send(message=notification)


@flow(name="git-repositories-create-branch", flow_run_name="Create branch '{branch}' in Git Repositories")
async def create_branch(branch: str, branch_id: str, service: InfrahubServices) -> None:
    """Request to the creation of git branches in available repositories."""
    await add_tags(branches=[branch])
    repositories: list[CoreRepository] = await service.client.filters(kind=CoreRepository)
    batch = await service.client.create_batch()
    for repository in repositories:
        batch.add(
            task=git_branch_create,
            client=service.client.client,
            branch=branch,
            branch_id=branch_id,
            repository_name=repository.name.value,
            repository_id=repository.id,
            repository_location=repository.location.value,
            service=service,
        )

    async for _, _ in batch.execute():
        pass


@flow(name="git_repositories_sync", flow_run_name="Sync Git Repositories")
async def sync_remote_repositories(service: InfrahubServices) -> None:
    log = get_run_logger()

    branches = await service.client.branch.all()
    repositories = await service.client.get_list_repositories(branches=branches, kind=InfrahubKind.REPOSITORY)

    for repo_name, repository_data in repositories.items():
        active_internal_status = RepositoryInternalStatus.ACTIVE.value
        default_internal_status = repository_data.branch_info[registry.default_branch].internal_status
        staging_branch = None
        if default_internal_status != RepositoryInternalStatus.ACTIVE.value:
            active_internal_status = RepositoryInternalStatus.STAGING.value
            staging_branch = repository_data.get_staging_branch()

        infrahub_branch = staging_branch or registry.default_branch

        async with lock.registry.get(name=repo_name, namespace="repository"):
            init_failed = False
            try:
                repo = await InfrahubRepository.init(
                    service=service,
                    id=repository_data.repository.id,
                    name=repository_data.repository.name.value,
                    location=repository_data.repository.location.value,
                    client=service.client,
                    internal_status=active_internal_status,
                    default_branch_name=repository_data.repository.default_branch.value,
                )
            except RepositoryError as exc:
                service.log.error(str(exc))
                init_failed = True

            if init_failed:
                try:
                    repo = await InfrahubRepository.new(
                        service=service,
                        id=repository_data.repository.id,
                        name=repository_data.repository.name.value,
                        location=repository_data.repository.location.value,
                        client=service.client,
                        internal_status=active_internal_status,
                        default_branch_name=repository_data.repository.default_branch.value,
                    )
                    await repo.import_objects_from_files(  # type: ignore[call-overload]
                        git_branch_name=registry.default_branch, infrahub_branch_name=infrahub_branch
                    )
                except RepositoryError as exc:
                    log.info(exc.message)
                    continue

            try:
                await repo.sync(staging_branch=staging_branch)
                # Tell workers to fetch to stay in sync
                message = messages.RefreshGitFetch(
                    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                    location=repository_data.repository.location.value,
                    repository_id=repository_data.repository.id,
                    repository_name=repository_data.repository.name.value,
                    repository_kind=repository_data.repository.get_kind(),
                    infrahub_branch_name=infrahub_branch,
                    infrahub_branch_id=branches[infrahub_branch].id,
                )
                await service.message_bus.send(message=message)
            except RepositoryError as exc:
                log.info(exc.message)


@task(  # type: ignore[arg-type]
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
    service: InfrahubServices,
) -> None:
    log = get_run_logger()
    repo = await InfrahubRepository.init(
        id=repository_id, name=repository_name, location=repository_location, client=client, service=service
    )

    async with lock.registry.get(name=repository_name, namespace="repository"):
        await repo.create_branch_in_git(branch_name=branch, branch_id=branch_id, push_origin=True)

        # New branch has been pushed remotely, tell workers to fetch it
        message = messages.RefreshGitFetch(
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
            location=repo.get_location(),
            repository_id=str(repo.id),
            repository_name=repo.name,
            repository_kind=InfrahubKind.REPOSITORY,
            infrahub_branch_name=branch,
            infrahub_branch_id=branch_id,
        )
        await service.message_bus.send(message=message)
        log.debug("Sent message to all workers to fetch the latest version of the repository (RefreshGitFetch)")


@flow(name="artifact-definition-generate", flow_run_name="Generate all artifacts")
async def generate_artifact_definition(branch: str, context: InfrahubContext, service: InfrahubServices) -> None:
    await add_branch_tag(branch_name=branch)

    artifact_definitions = await service.client.all(kind=CoreArtifactDefinition, branch=branch, include=["id"])

    for artifact_definition in artifact_definitions:
        model = RequestArtifactDefinitionGenerate(
            branch=branch,
            artifact_definition_id=artifact_definition.id,
            artifact_definition_name=artifact_definition.name.value,
        )
        await service.workflow.submit_workflow(
            workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, context=context, parameters={"model": model}
        )


@flow(name="artifact-generate", flow_run_name="Generate artifact {model.artifact_name}")
async def generate_artifact(model: RequestArtifactGenerate, service: InfrahubServices) -> None:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])
    log = get_run_logger()
    repo = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )

    artifact, artifact_created = await define_artifact(model=model, service=service)

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
    model: RequestArtifactDefinitionGenerate, context: InfrahubContext, service: InfrahubServices
) -> None:
    await add_tags(branches=[model.branch])

    artifact_definition = await service.client.get(
        kind=CoreArtifactDefinition, id=model.artifact_definition_id, branch=model.branch
    )

    await artifact_definition.targets.fetch()
    group = artifact_definition.targets.peer
    await group.members.fetch()
    current_members = [member.id for member in group.members.peers]

    existing_artifacts = await service.client.filters(
        kind=CoreArtifact,
        definition__ids=[model.artifact_definition_id],
        include=["object"],
        branch=model.branch,
    )
    artifacts_by_member = {}
    for artifact in existing_artifacts:
        if artifact.object.id in current_members:
            artifacts_by_member[artifact.object.peer.id] = artifact.id

    await artifact_definition.transformation.fetch()
    transformation_repository = artifact_definition.transformation.peer.repository

    await transformation_repository.fetch()

    transform = artifact_definition.transformation.peer
    await transform.query.fetch()
    query = transform.query.peer
    repository = transformation_repository.peer
    branch = await service.client.branch.get(branch_name=model.branch)
    if branch.sync_with_git:
        repository = await service.client.get(
            kind=InfrahubKind.GENERICREPOSITORY, id=repository.id, branch=model.branch, fragment=True
        )
    transform_location = ""

    if transform.typename == InfrahubKind.TRANSFORMJINJA2:
        transform_location = transform.template_path.value
    elif transform.typename == InfrahubKind.TRANSFORMPYTHON:
        transform_location = f"{transform.file_path.value}::{transform.class_name.value}"

    for relationship in group.members.peers:
        member = relationship.peer
        artifact_id = artifacts_by_member.get(member.id)
        if model.limit and artifact_id not in model.limit:
            continue

        request_artifact_generate_model = RequestArtifactGenerate(
            artifact_name=artifact_definition.artifact_name.value,
            artifact_id=artifact_id,
            artifact_definition=model.artifact_definition_id,
            commit=repository.commit.value,
            content_type=artifact_definition.content_type.value,
            transform_type=str(transform.typename),
            transform_location=transform_location,
            repository_id=repository.id,
            repository_name=repository.name.value,
            repository_kind=repository.get_kind(),
            branch_name=model.branch,
            query=query.name.value,
            variables=member.extract(params=artifact_definition.parameters.value),
            target_id=member.id,
            target_name=member.display_label,
            target_kind=member.get_kind(),
            timeout=transform.timeout.value,
            context=context,
        )

        await service.workflow.submit_workflow(
            workflow=REQUEST_ARTIFACT_GENERATE, context=context, parameters={"model": request_artifact_generate_model}
        )


@flow(name="git-repository-pull-read-only", flow_run_name="Pull latest commit on {model.repository_name}")
async def pull_read_only(model: GitRepositoryPullReadOnly, service: InfrahubServices) -> None:
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
                client=service.client,
                ref=model.ref,
                infrahub_branch_name=model.infrahub_branch_name,
                service=service,
            )
        except RepositoryError:
            init_failed = True

        if init_failed:
            repo = await InfrahubReadOnlyRepository.new(
                id=model.repository_id,
                name=model.repository_name,
                location=model.location,
                client=service.client,
                ref=model.ref,
                infrahub_branch_name=model.infrahub_branch_name,
                service=service,
            )

        await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name, commit=model.commit)  # type: ignore[call-overload]
        await repo.sync_from_remote(commit=model.commit)

        # Tell workers to fetch to stay in sync
        message = messages.RefreshGitFetch(
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
            location=model.location,
            repository_id=model.repository_id,
            repository_name=model.repository_name,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            infrahub_branch_name=model.infrahub_branch_name,
            infrahub_branch_id=model.infrahub_branch_id,
        )
        await service.message_bus.send(message=message)


@flow(
    name="git-repository-merge",
    flow_run_name="Merge {model.source_branch} > {model.destination_branch} in git repository",
)
async def merge_git_repository(model: GitRepositoryMerge, service: InfrahubServices) -> None:
    await add_tags(branches=[model.source_branch, model.destination_branch], nodes=[model.repository_id])

    repo = await InfrahubRepository.init(
        id=model.repository_id,
        name=model.repository_name,
        client=service.client,
        default_branch_name=model.default_branch,
        service=service,
    )

    if model.internal_status == RepositoryInternalStatus.STAGING.value:
        repo_source = await service.client.get(
            kind=InfrahubKind.GENERICREPOSITORY, id=model.repository_id, branch=model.source_branch
        )
        repo_main = await service.client.get(kind=InfrahubKind.GENERICREPOSITORY, id=model.repository_id)
        repo_main.internal_status.value = RepositoryInternalStatus.ACTIVE.value
        repo_main.sync_status.value = repo_source.sync_status.value

        commit = repo.get_commit_value(branch_name=repo.default_branch, remote=False)
        repo_main.commit.value = commit

        await repo_main.save()
    else:
        async with lock.registry.get(name=model.repository_name, namespace="repository"):
            await repo.merge(source_branch=model.source_branch, dest_branch=model.destination_branch)
            if repo.location:
                # Destination branch has changed and pushed remotely, tell workers to re-fetch
                message = messages.RefreshGitFetch(
                    meta=Meta(initiator_id=WORKER_IDENTITY, request_id=get_log_data().get("request_id", "")),
                    location=repo.location,
                    repository_id=str(repo.id),
                    repository_name=repo.name,
                    repository_kind=InfrahubKind.REPOSITORY,
                    infrahub_branch_name=model.destination_branch,
                    infrahub_branch_id=model.destination_branch_id,
                )
                await service.message_bus.send(message=message)


@flow(name="git-repository-import-object", flow_run_name="Import objects from git repository")
async def import_objects_from_git_repository(model: GitRepositoryImportObjects, service: InfrahubServices) -> None:
    await add_branch_tag(model.infrahub_branch_name)
    repo = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )
    await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name, commit=model.commit)  # type: ignore[call-overload]


@flow(
    name="git-repository-diff-names-only",
    flow_run_name="Collecting modifications between commits {model.first_commit} and {model.second_commit}",
    persist_result=True,
)
async def git_repository_diff_names_only(
    model: GitDiffNamesOnly, service: InfrahubServices
) -> GitDiffNamesOnlyResponse:
    repo = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
    )
    files_changed: list[str] = []
    files_removed: list[str] = []

    if model.second_commit:
        files_changed, files_added, files_removed = await repo.calculate_diff_between_commits(
            first_commit=model.first_commit, second_commit=model.second_commit
        )
    else:
        files_added = await repo.list_all_files(commit=model.first_commit)

    response = GitDiffNamesOnlyResponse(
        files_added=files_added, files_changed=files_changed, files_removed=files_removed
    )
    return response


@flow(
    name="git-repository-user-checks-definition-trigger",
    flow_run_name="Trigger user defined checks for repository {model.repository_name}",
)
async def trigger_repository_user_checks_definitions(
    model: UserCheckDefinitionData, context: InfrahubContext, service: InfrahubServices
) -> None:
    await add_tags(branches=[model.branch_name], nodes=[model.proposed_change])
    log = get_run_logger()

    definition = await service.client.get(
        kind=CoreCheckDefinition, id=model.check_definition_id, branch=model.branch_name
    )
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)
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
            service.log.info("Found the same validator", validator=previous_validator)

    validator = await start_validator(
        service=service,
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
        await definition.targets.fetch()
        group = definition.targets.peer
        await group.members.fetch()
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
                commit=model.commit,
                file_path=model.file_path,
                class_name=model.class_name,
                branch_name=model.branch_name,
                check_definition_id=model.check_definition_id,
                proposed_change=model.proposed_change,
                variables=member.extract(params=definition.parameters.value),
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

    checks_coroutines = [
        service.workflow.execute_workflow(
            workflow=GIT_REPOSITORY_USER_CHECK_RUN, parameters={"model": model}, expected_return=ValidatorConclusion
        )
        for model in check_models
    ]

    await run_checks_and_update_validator(
        checks=checks_coroutines,
        validator=validator,
        context=context,
        service=service,
        proposed_change_id=model.proposed_change,
    )


@flow(
    name="git-repository-trigger-user-checks",
    flow_run_name="Evaluating user-defined checks on repository {model.repository_name}",
)
async def trigger_user_checks(
    model: TriggerRepositoryUserChecks, service: InfrahubServices, context: InfrahubContext
) -> None:
    """Request to start validation checks on a specific repository for User-defined checks."""

    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])
    log = get_run_logger()

    repository = await service.client.get(
        kind=InfrahubKind.GENERICREPOSITORY, id=model.repository_id, branch=model.source_branch, fragment=True
    )
    await repository.checks.fetch()

    for relationship in repository.checks.peers:
        log.info("Adding check for user defined check")
        check_definition = relationship.peer
        user_check_definition_model = UserCheckDefinitionData(
            check_definition_id=check_definition.id,
            repository_id=repository.id,
            repository_name=repository.name.value,
            commit=repository.commit.value,
            file_path=check_definition.file_path.value,
            class_name=check_definition.class_name.value,
            branch_name=model.source_branch,
            proposed_change=model.proposed_change,
            branch_diff=model.branch_diff,
        )
        await service.workflow.submit_workflow(
            workflow=GIT_REPOSITORY_USER_CHECKS_DEFINITIONS_TRIGGER,
            context=context,
            parameters={"model": user_check_definition_model},
        )


@flow(
    name="git-repository-trigger-internal-checks",
    flow_run_name="Running repository checks for repository {model.repository}",
)
async def trigger_internal_checks(
    model: TriggerRepositoryInternalChecks, service: InfrahubServices, context: InfrahubContext
) -> None:
    """Request to start validation checks on a specific repository."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])
    log = get_run_logger()

    repository = await service.client.get(
        kind=InfrahubKind.GENERICREPOSITORY, id=model.repository, branch=model.source_branch
    )
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)

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
        ):
            previous_validator = existing_validator

    validator = await start_validator(
        service=service,
        validator=previous_validator,
        validator_type=CoreRepositoryValidator,
        proposed_change=model.proposed_change,
        data={
            "label": validator_name,
            "repository": model.repository,
        },
        context=context,
    )

    check_execution_id = str(UUIDT())
    check_execution_ids.append(check_execution_id)
    log.info("Adding check for merge conflict")
    checks_in_execution = ",".join(check_execution_ids)
    log.info(f"Checks in execution {checks_in_execution}")

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
    check_coroutine = service.workflow.execute_workflow(
        workflow=GIT_REPOSITORY_MERGE_CONFLICTS_CHECKS_RUN,
        parameters={"model": check_merge_conflict_model},
        expected_return=ValidatorConclusion,
    )

    await run_checks_and_update_validator(
        checks=[check_coroutine],
        validator=validator,
        context=context,
        service=service,
        proposed_change_id=model.proposed_change,
    )


@flow(
    name="git-repository-check-merge-conflict",
    flow_run_name="Check for merge conflicts between {model.source_branch} and {model.target_branch}",
)
async def run_check_merge_conflicts(
    model: CheckRepositoryMergeConflicts, service: InfrahubServices
) -> ValidatorConclusion:
    """Runs a check to see if there are merge conflicts between two branches."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    success_condition = "-"
    validator = await service.client.get(kind=InfrahubKind.REPOSITORYVALIDATOR, id=model.validator_id)
    await validator.checks.fetch()

    repo = await InfrahubRepository.init(id=model.repository_id, name=model.repository_name, service=service)
    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        conflicts = await repo.get_conflicts(source_branch=model.source_branch, dest_branch=model.target_branch)

    existing_checks = {}
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if existing_check.typename == InfrahubKind.FILECHECK and existing_check.kind.value == "MergeConflictCheck":
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
                check = await service.client.create(
                    kind=InfrahubKind.FILECHECK,
                    data={
                        "name": conflict,
                        "origin": "ConflictCheck",
                        "kind": "MergeConflictCheck",
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
        check = await service.client.create(
            kind=InfrahubKind.FILECHECK,
            data={
                "name": "Merge Conflict Check",
                "origin": "ConflictCheck",
                "kind": "MergeConflictCheck",
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "conclusion": validator_conclusion.value,
                "severity": "info",
            },
        )
        await check.save()

    async with service.database.start_session() as db:
        await NodeManager.delete(db=db, nodes=list(existing_checks.values()))

    return validator_conclusion


@flow(name="git-repository-run-user-check", flow_run_name="Execute user defined Check '{model.name}'")
async def run_user_check(model: UserCheckData, service: InfrahubServices) -> ValidatorConclusion:
    await add_tags(branches=[model.branch_name], nodes=[model.proposed_change])
    log = get_run_logger()

    validator = await service.client.get(kind=InfrahubKind.USERVALIDATOR, id=model.validator_id)
    await validator.checks.fetch()

    repo = await InfrahubRepository.init(
        id=model.repository_id, name=model.repository_name, commit=model.commit, service=service
    )
    conclusion = ValidatorConclusion.FAILURE
    severity = "critical"
    try:
        check_run = await repo.execute_python_check.with_options(timeout_seconds=model.timeout)(
            branch_name=model.branch_name,
            location=model.file_path,
            class_name=model.class_name,
            client=service.client,
            commit=model.commit,
            params=model.variables,
        )  # type: ignore[misc]
        if check_run.passed:
            conclusion = ValidatorConclusion.SUCCESS
            severity = "info"
            log.info("The check passed")
        else:
            log.warning("The check reported failures")
            for log_entry in check_run.log_entries:
                log.warning(log_entry)
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
        check = await service.client.create(
            kind=InfrahubKind.STANDARDCHECK,
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

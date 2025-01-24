from datetime import timedelta

from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreArtifact, CoreArtifactDefinition, CoreRepository
from prefect import flow, task
from prefect.automations import AutomationCore
from prefect.cache_policies import NONE
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.exceptions import RepositoryError
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import COMPUTED_ATTRIBUTE_SETUP_PYTHON

from ..log import get_log_data
from ..tasks.artifact import define_artifact
from ..workflows.catalogue import REQUEST_ARTIFACT_DEFINITION_GENERATE, REQUEST_ARTIFACT_GENERATE
from ..workflows.utils import add_branch_tag, add_tags
from .constants import AUTOMATION_NAME
from .models import (
    GitDiffNamesOnly,
    GitDiffNamesOnlyResponse,
    GitRepositoryAdd,
    GitRepositoryAddReadOnly,
    GitRepositoryImportObjects,
    GitRepositoryMerge,
    GitRepositoryPullReadOnly,
    RequestArtifactDefinitionGenerate,
    RequestArtifactGenerate,
)
from .repository import InfrahubReadOnlyRepository, InfrahubRepository, get_initialized_repo


@flow(
    name="git-repository-add-read-write",
    flow_run_name="Adding repository {model.repository_name} in branch {model.infrahub_branch_name}",
)
async def add_git_repository(model: GitRepositoryAdd) -> None:
    service = services.service
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
        )
        await repo.import_objects_from_files(
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
            await service.send(message=notification)


@flow(
    name="git-repository-add-read-only",
    flow_run_name="Adding read only repository {model.repository_name} in branch {model.infrahub_branch_name}",
)
async def add_git_repository_read_only(model: GitRepositoryAddReadOnly) -> None:
    service = services.service
    await add_tags(branches=[model.infrahub_branch_name], nodes=[model.repository_id])

    async with lock.registry.get(name=model.repository_name, namespace="repository"):
        repo = await InfrahubReadOnlyRepository.new(
            id=model.repository_id,
            name=model.repository_name,
            location=model.location,
            client=service.client,
            ref=model.ref,
            infrahub_branch_name=model.infrahub_branch_name,
        )
        await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name)
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
            await service.send(message=notification)


@flow(name="git-repositories-create-branch", flow_run_name="Create branch '{branch}' in Git Repositories")
async def create_branch(branch: str, branch_id: str) -> None:
    """Request to the creation of git branches in available repositories."""
    service = services.service
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
        )

    async for _, _ in batch.execute():
        pass


@flow(name="git_repositories_sync", flow_run_name="Sync Git Repositories")
async def sync_remote_repositories() -> None:
    service = services.service

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
                    await repo.import_objects_from_files(
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
                await service.send(message=message)
            except RepositoryError as exc:
                log.info(exc.message)


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
) -> None:
    service = services.service
    log = get_run_logger()
    repo = await InfrahubRepository.init(
        id=repository_id, name=repository_name, location=repository_location, client=client
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
        await service.send(message=message)
        log.debug("Sent message to all workers to fetch the latest version of the repository (RefreshGitFetch)")


@flow(name="artifact-definition-generate", flow_run_name="Generate all artifacts")
async def generate_artifact_definition(branch: str) -> None:
    service = services.service
    await add_branch_tag(branch_name=branch)

    artifact_definitions = await service.client.all(kind=CoreArtifactDefinition, branch=branch, include=["id"])

    for artifact_definition in artifact_definitions:
        model = RequestArtifactDefinitionGenerate(
            branch=branch,
            artifact_definition_id=artifact_definition.id,
            artifact_definition_name=artifact_definition.name.value,
        )
        await service.workflow.submit_workflow(
            workflow=REQUEST_ARTIFACT_DEFINITION_GENERATE, parameters={"model": model}
        )


@flow(name="artifact-generate", flow_run_name="Generate artifact {model.artifact_name}")
async def generate_artifact(model: RequestArtifactGenerate) -> None:
    service = services.service

    await add_tags(branches=[model.branch_name], nodes=[model.target_id])
    log = get_run_logger()
    repo = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )

    artifact = await define_artifact(message=model, service=service)

    try:
        result = await repo.render_artifact(artifact=artifact, message=model)
        log.debug(
            f"Generated artifact | changed: {result.changed} | {result.checksum} | {result.storage_id}",
        )
    except Exception:  # pylint: disable=broad-except
        log.exception("Failed to generate artifact")
        artifact.status.value = "Error"
        await artifact.save()
        raise


@flow(
    name="request_artifact_definitions_generate",
    flow_run_name="Trigger Generation of Artifacts for {model.artifact_definition_name}",
)
async def generate_request_artifact_definition(model: RequestArtifactDefinitionGenerate) -> None:
    service = services.service
    await add_tags(branches=[model.branch], nodes=[model.artifact_definition_id])

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
            timeout=transform.timeout.value,
        )

        await service.workflow.submit_workflow(
            workflow=REQUEST_ARTIFACT_GENERATE, parameters={"model": request_artifact_generate_model}
        )


@flow(name="git-repository-pull-read-only", flow_run_name="Pull latest commit on {model.repository_name}")
async def pull_read_only(model: GitRepositoryPullReadOnly) -> None:
    service = services.service

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
            )

        await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name, commit=model.commit)
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
        await service.send(message=message)


@flow(
    name="git-repository-merge",
    flow_run_name="Merge {model.source_branch} > {model.destination_branch} in git repository",
)
async def merge_git_repository(model: GitRepositoryMerge) -> None:
    service = services.service

    await add_tags(branches=[model.source_branch, model.destination_branch], nodes=[model.repository_id])

    repo = await InfrahubRepository.init(
        id=model.repository_id,
        name=model.repository_name,
        client=service.client,
        default_branch_name=model.default_branch,
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
                await service.send(message=message)


@flow(name="git-commit-automation-setup", flow_run_name="Setup git commit updated event in task-manager")
async def setup_commit_automation() -> None:
    log = get_run_logger()

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(
                    name=DeploymentFilterName(any_=[COMPUTED_ATTRIBUTE_SETUP_PYTHON.name])
                )
            )
        }
        if COMPUTED_ATTRIBUTE_SETUP_PYTHON.name not in deployments:
            raise ValueError("Unable to find the deployment for COMPUTED_ATTRIBUTE_SETUP_PYTHON")

        deployment_id_computed_attribute_setup_python = deployments[COMPUTED_ATTRIBUTE_SETUP_PYTHON.name].id

        schema_update_automation = await client.find_automation(id_or_name=AUTOMATION_NAME)

        automation = AutomationCore(
            name=AUTOMATION_NAME,
            description="Trigger actions on schema update event",
            enabled=True,
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"infrahub.repository.update_commit"},
                within=timedelta(0),
                threshold=1,
            ),
            actions=[
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_computed_attribute_setup_python,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                        "commit": "{{ event.payload['commit'] }}",
                    },
                    job_variables={},
                ),
            ],
        )

        if schema_update_automation:
            await client.update_automation(automation_id=schema_update_automation.id, automation=automation)
            log.info(f"{AUTOMATION_NAME} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{AUTOMATION_NAME} Created")


@flow(name="git-repository-import-object", flow_run_name="Import objects from git repository")
async def import_objects_from_git_repository(model: GitRepositoryImportObjects) -> None:
    await add_branch_tag(model.infrahub_branch_name)
    repo = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=services.service,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )
    await repo.import_objects_from_files(infrahub_branch_name=model.infrahub_branch_name, commit=model.commit)


@flow(
    name="git-repository-diff-names-only",
    flow_run_name="Collecting modifications between commits {model.first_commit} and {model.second_commit}",
    persist_result=True,
)
async def git_repository_diff_names_only(model: GitDiffNamesOnly) -> GitDiffNamesOnlyResponse:
    service = services.service

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

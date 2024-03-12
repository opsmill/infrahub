from typing import List, Optional

from infrahub_sdk import UUIDT

from infrahub.core.constants import InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check(message: messages.RequestArtifactDefinitionCheck, service: InfrahubServices) -> None:
    async with service.task_report(
        title=f"Artifact Definition: {message.artifact_definition.definition_name}",
        related_node=message.proposed_change,
    ) as task_report:
        log.info(
            "Validating generation of artifacts",
            artifact_definition=message.artifact_definition.definition_id,
            source_branch=message.source_branch,
        )
        events: List[InfrahubMessage] = []

        artifact_definition = await service.client.get(
            kind=InfrahubKind.ARTIFACTDEFINITION,
            id=message.artifact_definition.definition_id,
            branch=message.source_branch,
        )
        proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

        validator_name = f"Artifact Validator: {message.artifact_definition.definition_name}"
        validator_execution_id = str(UUIDT())
        check_execution_ids: List[str] = []

        await proposed_change.validations.fetch()

        validator = None
        for relationship in proposed_change.validations.peers:
            existing_validator = relationship.peer
            if (
                existing_validator.typename == InfrahubKind.ARTIFACTVALIDATOR
                and existing_validator.definition.id == message.artifact_definition.definition_id
            ):
                validator = existing_validator

        if validator:
            validator.conclusion.value = ValidatorConclusion.UNKNOWN.value
            validator.state.value = ValidatorState.QUEUED.value
            validator.started_at.value = ""
            validator.completed_at.value = ""
            await validator.save()
        else:
            validator = await service.client.create(
                kind=InfrahubKind.ARTIFACTVALIDATOR,
                data={
                    "label": validator_name,
                    "proposed_change": message.proposed_change,
                    "definition": message.artifact_definition.definition_id,
                },
            )
            await validator.save()

        await artifact_definition.targets.fetch()
        group = artifact_definition.targets.peer
        await group.members.fetch()

        existing_artifacts = await service.client.filters(
            kind=InfrahubKind.ARTIFACT,
            definition__ids=[message.artifact_definition.definition_id],
            include=["object"],
            branch=message.source_branch,
        )
        artifacts_by_member = {}
        for artifact in existing_artifacts:
            artifacts_by_member[artifact.object.peer.id] = artifact.id

        repository = message.branch_diff.get_repository(repository_id=message.artifact_definition.repository_id)
        requested_artifacts = 0
        impacted_artifacts = message.branch_diff.get_subscribers_ids(kind=InfrahubKind.ARTIFACT)
        for relationship in group.members.peers:
            member = relationship.peer
            artifact_id = artifacts_by_member.get(member.id)
            if _render_artifact(
                artifact_id=artifact_id,
                managed_branch=message.source_branch_sync_with_git,
                impacted_artifacts=impacted_artifacts,
            ):
                check_execution_id = str(UUIDT())
                check_execution_ids.append(check_execution_id)
                requested_artifacts += 1
                events.append(
                    messages.CheckArtifactCreate(
                        artifact_name=message.artifact_definition.definition_name,
                        artifact_id=artifact_id,
                        artifact_definition=message.artifact_definition.definition_id,
                        commit=repository.source_commit,
                        content_type=message.artifact_definition.content_type,
                        transform_type=message.artifact_definition.transform_kind,
                        transform_location=message.artifact_definition.transform_location,
                        repository_id=repository.repository_id,
                        repository_name=repository.repository_name,
                        repository_kind=repository.kind,
                        branch_name=message.source_branch,
                        query=message.artifact_definition.query_name,
                        variables=member.extract(params=artifact_definition.parameters.value),
                        target_id=member.id,
                        target_name=member.name.value,
                        timeout=message.artifact_definition.timeout,
                        validator_id=validator.id,
                        meta=Meta(validator_execution_id=validator_execution_id, check_execution_id=check_execution_id),
                    )
                )

        checks_in_execution = ",".join(check_execution_ids)
        await service.cache.set(
            key=f"validator_execution_id:{validator_execution_id}:checks", value=checks_in_execution, expires=7200
        )
        events.append(
            messages.FinalizeValidatorExecution(
                start_time=Timestamp().to_string(),
                validator_id=validator.id,
                validator_execution_id=validator_execution_id,
                validator_type=InfrahubKind.ARTIFACTVALIDATOR,
            )
        )
        await task_report.info(event=f"{requested_artifacts} artifact(s) requires to be generated.")
        for event in events:
            event.assign_meta(parent=message)
            await service.send(message=event)


async def generate(message: messages.RequestArtifactDefinitionGenerate, service: InfrahubServices) -> None:
    log.info(
        "Received request to generate artifacts for an artifact_definition",
        branch=message.branch,
        artifact_definition=message.artifact_definition,
        limit=message.limit,
    )
    artifact_definition = await service.client.get(
        kind=InfrahubKind.ARTIFACTDEFINITION, id=message.artifact_definition, branch=message.branch
    )

    await artifact_definition.targets.fetch()
    group = artifact_definition.targets.peer
    await group.members.fetch()

    existing_artifacts = await service.client.filters(
        kind=InfrahubKind.ARTIFACT,
        definition__ids=[message.artifact_definition],
        include=["object"],
        branch=message.branch,
    )
    artifacts_by_member = {}
    for artifact in existing_artifacts:
        artifacts_by_member[artifact.object.peer.id] = artifact.id

    await artifact_definition.transformation.fetch()
    transformation_repository = artifact_definition.transformation.peer.repository

    await transformation_repository.fetch()

    transform = artifact_definition.transformation.peer
    await transform.query.fetch()
    query = transform.query.peer
    repository = transformation_repository.peer
    branch = await service.client.branch.get(branch_name=message.branch)
    if branch.sync_with_git:
        repository = await service.client.get(
            kind=InfrahubKind.GENERICREPOSITORY, id=repository.id, branch=message.branch, fragment=True
        )
    transform_location = ""

    if transform.typename == InfrahubKind.TRANSFORMJINJA2:
        transform_location = transform.template_path.value
    elif transform.typename == "CoreTransformPython":
        transform_location = f"{transform.file_path.value}::{transform.class_name.value}"

    events = []
    for relationship in group.members.peers:
        member = relationship.peer
        artifact_id = artifacts_by_member.get(member.id)
        if message.limit and artifact_id not in message.limit:
            continue

        events.append(
            messages.RequestArtifactGenerate(
                artifact_name=artifact_definition.name.value,
                artifact_id=artifact_id,
                artifact_definition=message.artifact_definition,
                commit=repository.commit.value,
                content_type=artifact_definition.content_type.value,
                transform_type=transform.typename,
                transform_location=transform_location,
                repository_id=repository.id,
                repository_name=repository.name.value,
                repository_kind=repository.get_kind(),
                branch_name=message.branch,
                query=query.name.value,
                variables=member.extract(params=artifact_definition.parameters.value),
                target_id=member.id,
                target_name=member.name.value,
                timeout=transform.timeout.value,
            )
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


def _render_artifact(artifact_id: Optional[str], managed_branch: bool, impacted_artifacts: list[str]) -> bool:
    """Returns a boolean to indicate if an artifact should be generated or not.
    Will return true if:
        * The artifact_id wasn't set which could be that it's a new object that doesn't have a previous artifact
        * The source brance is not data only which would indicate that it could contain updates in git to the transform
        * The artifact_id exists in the impaced_artifacts list
    Will return false if:
        * The source branch is a data only branch and the artifact_id exists and is not in the impacted list
    """
    if not artifact_id or managed_branch:
        return True
    return artifact_id in impacted_artifacts

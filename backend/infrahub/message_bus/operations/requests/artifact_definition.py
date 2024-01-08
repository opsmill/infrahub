from typing import List

from infrahub_sdk import UUIDT

from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.services import InfrahubServices

log = get_logger()


async def check(  # pylint: disable=too-many-statements
    message: messages.RequestArtifactDefinitionCheck, service: InfrahubServices
) -> None:
    log.info(
        "Validating generation of artifacts",
        artifact_definition=message.artifact_definition,
        source_branch=message.source_branch,
    )
    events: List[InfrahubMessage] = []

    artifact_definition = await service.client.get(
        kind="CoreArtifactDefinition", id=message.artifact_definition, branch=message.source_branch
    )
    proposed_change = await service.client.get(kind="CoreProposedChange", id=message.proposed_change)

    validator_name = f"Artifact Validator: {artifact_definition.name.value}"
    validator_execution_id = str(UUIDT())
    check_execution_ids: List[str] = []

    await proposed_change.validations.fetch()

    validator = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer
        if (
            existing_validator.typename == "CoreArtifactValidator"
            and existing_validator.definition.id == message.artifact_definition
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
            kind="CoreArtifactValidator",
            data={
                "label": validator_name,
                "proposed_change": message.proposed_change,
                "definition": message.artifact_definition,
            },
        )
        await validator.save()

    await artifact_definition.targets.fetch()
    group = artifact_definition.targets.peer
    await group.members.fetch()

    existing_artifacts = await service.client.filters(
        kind="CoreArtifact",
        definition__ids=[message.artifact_definition],
        include=["object"],
        branch=message.source_branch,
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
    branch = await service.client.branch.get(branch_name=message.source_branch)
    if not branch.is_data_only:
        repository = await service.client.get(kind="CoreRepository", id=repository.id, branch=message.source_branch)
    transform_location = ""

    if transform.typename == "CoreRFile":
        transform_location = transform.template_path.value
    elif transform.typename == "CoreTransformPython":
        transform_location = f"{transform.file_path.value}::{transform.class_name.value}"

    for relationship in group.members.peers:
        member = relationship.peer
        check_execution_id = str(UUIDT())
        check_execution_ids.append(check_execution_id)

        events.append(
            messages.CheckArtifactCreate(
                artifact_name=artifact_definition.name.value,
                artifact_id=artifacts_by_member.get(member.id),
                artifact_definition=message.artifact_definition,
                commit=repository.commit.value,
                content_type=artifact_definition.content_type.value,
                transform_type=transform.typename,
                transform_location=transform_location,
                repository_id=repository.id,
                repository_name=repository.name.value,
                branch_name=message.source_branch,
                query=query.query.value,
                variables=member.extract(params=artifact_definition.parameters.value),
                target_id=member.id,
                target_name=member.name.value,
                timeout=transform.timeout.value,
                rebase=transform.rebase.value,
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
            validator_type="CoreArtifactValidator",
        )
    )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def generate(message: messages.RequestArtifactDefinitionGenerate, service: InfrahubServices) -> None:
    log.info(
        f"Received request to generate artifacts for artifact_definition={message.artifact_definition}",
        branch=message.branch,
        limit=message.limit,
    )
    artifact_definition = await service.client.get(
        kind="CoreArtifactDefinition", id=message.artifact_definition, branch=message.branch
    )

    await artifact_definition.targets.fetch()
    group = artifact_definition.targets.peer
    await group.members.fetch()

    existing_artifacts = await service.client.filters(
        kind="CoreArtifact",
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
    if not branch.is_data_only:
        repository = await service.client.get(kind="CoreRepository", id=repository.id, branch=message.branch)
    transform_location = ""

    if transform.typename == "CoreRFile":
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
                branch_name=message.branch,
                query=query.name.value,
                variables=member.extract(params=artifact_definition.parameters.value),
                target_id=member.id,
                target_name=member.name.value,
                timeout=transform.timeout.value,
                rebase=transform.rebase.value,
            )
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)

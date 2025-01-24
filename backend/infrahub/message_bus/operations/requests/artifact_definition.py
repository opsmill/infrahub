from typing import Optional

from infrahub_sdk.uuidt import UUIDT
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.core.constants import InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.message_bus.types import KVTTL
from infrahub.services import InfrahubServices
from infrahub.workflows.utils import add_tags


@flow(
    name="artifact-definition-check",
    flow_run_name="Validating generation of artifacts for {message.artifact_definition.definition_name}",
)
async def check(message: messages.RequestArtifactDefinitionCheck, service: InfrahubServices) -> None:
    events: list[InfrahubMessage] = []
    await add_tags(branches=[message.source_branch], nodes=[message.proposed_change], db_change=True)

    log = get_run_logger()
    artifact_definition = await service.client.get(
        kind=InfrahubKind.ARTIFACTDEFINITION,
        id=message.artifact_definition.definition_id,
        branch=message.source_branch,
    )
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

    validator_name = f"Artifact Validator: {message.artifact_definition.definition_name}"
    validator_execution_id = str(UUIDT())
    check_execution_ids: list[str] = []

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
            log.info(f"Trigger Artifact processing for {member.display_label}")
            events.append(
                messages.CheckArtifactCreate(
                    artifact_name=message.artifact_definition.artifact_name,
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
                    target_name=member.display_label,
                    timeout=message.artifact_definition.timeout,
                    validator_id=validator.id,
                    meta=Meta(validator_execution_id=validator_execution_id, check_execution_id=check_execution_id),
                )
            )

    checks_in_execution = ",".join(check_execution_ids)
    await service.cache.set(
        key=f"validator_execution_id:{validator_execution_id}:checks",
        value=checks_in_execution,
        expires=KVTTL.TWO_HOURS,
    )
    events.append(
        messages.FinalizeValidatorExecution(
            start_time=Timestamp().to_string(),
            validator_id=validator.id,
            validator_execution_id=validator_execution_id,
            validator_type=InfrahubKind.ARTIFACTVALIDATOR,
        )
    )
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


def _render_artifact(artifact_id: Optional[str], managed_branch: bool, impacted_artifacts: list[str]) -> bool:  # pylint: disable=unused-argument
    """Returns a boolean to indicate if an artifact should be generated or not.
    Will return true if:
        * The artifact_id wasn't set which could be that it's a new object that doesn't have a previous artifact
        * The source brance is not data only which would indicate that it could contain updates in git to the transform
        * The artifact_id exists in the impacted_artifacts list
    Will return false if:
        * The source branch is a data only branch and the artifact_id exists and is not in the impacted list
    """

    # if not artifact_id or managed_branch:
    #    return True
    # return artifact_id in impacted_artifacts
    # Temporary workaround tracked in https://github.com/opsmill/infrahub/issues/4991
    return True

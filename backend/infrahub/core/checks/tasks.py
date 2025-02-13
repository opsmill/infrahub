from typing import Optional, Union

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.core.checks.models import CheckArtifactCreate, RequestArtifactDefinitionCheck
from infrahub.core.constants import InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.checks_runner import run_checks_and_update_validator
from infrahub.git import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.services import InfrahubServices
from infrahub.tasks.artifact import define_artifact
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE
from infrahub.workflows.utils import add_tags


@flow(
    name="artifact-definition-check",
    flow_run_name="Validating generation of artifacts for {model.artifact_definition.definition_name}",
)
async def check(model: RequestArtifactDefinitionCheck, service: InfrahubServices) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change], db_change=True)

    log = get_run_logger()
    artifact_definition = await service.client.get(
        kind=InfrahubKind.ARTIFACTDEFINITION,
        id=model.artifact_definition.definition_id,
        branch=model.source_branch,
    )
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)

    validator_name = f"Artifact Validator: {model.artifact_definition.definition_name}"

    await proposed_change.validations.fetch()

    validator = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer
        if (
            existing_validator.typename == InfrahubKind.ARTIFACTVALIDATOR
            and existing_validator.definition.id == model.artifact_definition.definition_id
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
                "proposed_change": model.proposed_change,
                "definition": model.artifact_definition.definition_id,
            },
        )
        await validator.save()

    await artifact_definition.targets.fetch()
    group = artifact_definition.targets.peer
    await group.members.fetch()

    existing_artifacts = await service.client.filters(
        kind=InfrahubKind.ARTIFACT,
        definition__ids=[model.artifact_definition.definition_id],
        include=["object"],
        branch=model.source_branch,
    )
    artifacts_by_member = {}
    for artifact in existing_artifacts:
        artifacts_by_member[artifact.object.peer.id] = artifact.id

    repository = model.branch_diff.get_repository(repository_id=model.artifact_definition.repository_id)
    impacted_artifacts = model.branch_diff.get_subscribers_ids(kind=InfrahubKind.ARTIFACT)

    checks = []

    for relationship in group.members.peers:
        member = relationship.peer
        artifact_id = artifacts_by_member.get(member.id)
        if _render_artifact(
            artifact_id=artifact_id,
            managed_branch=model.source_branch_sync_with_git,
            impacted_artifacts=impacted_artifacts,
        ):
            log.info(f"Trigger Artifact processing for {member.display_label}")

            check_model = CheckArtifactCreate(
                artifact_name=model.artifact_definition.artifact_name,
                artifact_id=artifact_id,
                artifact_definition=model.artifact_definition.definition_id,
                commit=repository.source_commit,
                content_type=model.artifact_definition.content_type,
                transform_type=model.artifact_definition.transform_kind,
                transform_location=model.artifact_definition.transform_location,
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
                repository_kind=repository.kind,
                branch_name=model.source_branch,
                query=model.artifact_definition.query_name,
                variables=member.extract(params=artifact_definition.parameters.value),
                target_id=member.id,
                target_name=member.display_label,
                timeout=model.artifact_definition.timeout,
                validator_id=validator.id,
            )

            checks.append(
                service.workflow.submit_workflow(
                    workflow=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, parameters={"model": check_model}
                )
            )

    await run_checks_and_update_validator(checks, validator)


def _render_artifact(artifact_id: Optional[str], managed_branch: bool, impacted_artifacts: list[str]) -> bool:  # noqa: ARG001
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


@flow(name="git-repository-check-artifact-create", flow_run_name="Check artifact creation")
async def create(model: CheckArtifactCreate, service: InfrahubServices) -> str:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])
    validator = await service.client.get(kind=InfrahubKind.ARTIFACTVALIDATOR, id=model.validator_id, include=["checks"])

    repo: InfrahubReadOnlyRepository | InfrahubRepository
    if InfrahubKind.READONLYREPOSITORY:
        repo = await InfrahubReadOnlyRepository.init(
            id=model.repository_id,
            name=model.repository_name,
            client=service.client,
            service=service,
        )
    else:
        repo = await InfrahubRepository.init(
            id=model.repository_id,
            name=model.repository_name,
            client=service.client,
            service=service,
        )

    artifact = await define_artifact(model=model, service=service)

    conclusion = ValidatorConclusion.SUCCESS.value
    severity = "info"
    artifact_result: dict[str, Union[str, bool, None]] = {
        "changed": None,
        "checksum": None,
        "artifact_id": None,
        "storage_id": None,
    }
    check_message = "Failed to render artifact"

    try:
        result = await repo.render_artifact(artifact=artifact, message=model)
        artifact_result["changed"] = result.changed
        artifact_result["checksum"] = result.checksum
        artifact_result["artifact_id"] = result.artifact_id
        artifact_result["storage_id"] = result.storage_id
        check_message = "Artifact rendered successfully"

    except Exception as exc:
        conclusion = ValidatorConclusion.FAILURE.value
        artifact.status.value = "Error"
        severity = "critical"
        check_message += f": {str(exc)}"
        await artifact.save()

    check = None
    check_name = f"{model.artifact_name}: {model.target_name}"
    existing_check = await service.client.filters(
        kind=InfrahubKind.ARTIFACTCHECK, validator__ids=validator.id, name__value=check_name
    )
    if existing_check:
        check = existing_check[0]

    if check:
        check.created_at.value = Timestamp().to_string()
        check.conclusion.value = conclusion
        check.severity.value = severity
        check.changed.value = artifact_result["changed"]
        check.checksum.value = artifact_result["checksum"]
        check.artifact_id.value = artifact_result["artifact_id"]
        check.storage_id.value = artifact_result["storage_id"]
        await check.save()
    else:
        check = await service.client.create(
            kind=InfrahubKind.ARTIFACTCHECK,
            data={
                "name": check_name,
                "origin": model.repository_id,
                "kind": "ArtifactDefinition",
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "message": check_message,
                "conclusion": conclusion,
                "severity": severity,
                "changed": artifact_result["changed"],
                "checksum": artifact_result["checksum"],
                "artifact_id": artifact_result["artifact_id"],
                "storage_id": artifact_result["storage_id"],
            },
        )
        await check.save()

    return conclusion

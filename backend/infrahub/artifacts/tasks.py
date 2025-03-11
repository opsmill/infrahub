from prefect import flow

from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.services import InfrahubServices
from infrahub.tasks.artifact import define_artifact
from infrahub.workflows.utils import add_tags


@flow(name="git-repository-check-artifact-create", flow_run_name="Check artifact creation")
async def create(model: CheckArtifactCreate, service: InfrahubServices) -> ValidatorConclusion:
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

    artifact, artifact_created = await define_artifact(model=model, service=service)

    severity = "info"
    artifact_result: dict[str, str | bool | None] = {
        "changed": None,
        "checksum": None,
        "artifact_id": None,
        "storage_id": None,
    }
    check_message = "Failed to render artifact"

    try:
        result = await repo.render_artifact(artifact=artifact, artifact_created=artifact_created, message=model)
        artifact_result["changed"] = result.changed
        artifact_result["checksum"] = result.checksum
        artifact_result["artifact_id"] = result.artifact_id
        artifact_result["storage_id"] = result.storage_id
        check_message = "Artifact rendered successfully"
        conclusion = ValidatorConclusion.SUCCESS

    except Exception as exc:
        artifact.status.value = "Error"
        await artifact.save()
        severity = "critical"
        conclusion = ValidatorConclusion.FAILURE
        check_message += f": {str(exc)}"

    check = None
    check_name = f"{model.artifact_name}: {model.target_name}"
    existing_check = await service.client.filters(
        kind=InfrahubKind.ARTIFACTCHECK, validator__ids=validator.id, name__value=check_name
    )
    if existing_check:
        check = existing_check[0]

    if check:
        check.created_at.value = Timestamp().to_string()
        check.conclusion.value = conclusion.value
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
                "conclusion": conclusion.value,
                "severity": severity,
                "changed": artifact_result["changed"],
                "checksum": artifact_result["checksum"],
                "artifact_id": artifact_result["artifact_id"],
                "storage_id": artifact_result["storage_id"],
            },
        )
        await check.save()

    return conclusion

from prefect import flow

from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git.repository import get_initialized_repo
from infrahub.tasks.artifact import define_artifact
from infrahub.workers.dependencies import get_client
from infrahub.workflows.utils import add_tags


@flow(name="git-repository-check-artifact-create", flow_run_name="Check artifact creation")
async def create(model: CheckArtifactCreate) -> ValidatorConclusion:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])

    client = get_client()

    validator = await client.get(kind=InfrahubKind.ARTIFACTVALIDATOR, id=model.validator_id, include=["checks"])

    repo = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )

    artifact, artifact_created = await define_artifact(model=model)

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
    existing_check = await client.filters(
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
        check = await client.create(
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

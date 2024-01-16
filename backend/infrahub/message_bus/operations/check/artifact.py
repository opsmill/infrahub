from typing import Dict, Union

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.artifact import define_artifact
from infrahub.tasks.check import set_check_status

log = get_logger()


async def create(message: messages.CheckArtifactCreate, service: InfrahubServices):
    log.debug("Creating artifact", message=message)
    validator = await service.client.get(
        kind=InfrahubKind.ARTIFACTVALIDATOR, id=message.validator_id, include=["checks"]
    )

    if InfrahubKind.READONLYREPOSITORY:
        repo = await InfrahubReadOnlyRepository.init(
            id=message.repository_id, name=message.repository_name, client=service.client
        )
    else:
        repo = await InfrahubRepository.init(
            id=message.repository_id, name=message.repository_name, client=service.client
        )

    artifact = await define_artifact(message=message, service=service)

    conclusion = ValidatorConclusion.SUCCESS.value
    severity = "info"
    artifact_result: Dict[str, Union[str, bool, None]] = {
        "changed": None,
        "checksum": None,
        "artifact_id": None,
        "storage_id": None,
    }
    check_message = "Failed to render artifact"

    try:
        result = await repo.render_artifact(artifact=artifact, message=message)
        artifact_result["changed"] = result.changed
        artifact_result["checksum"] = result.checksum
        artifact_result["artifact_id"] = result.artifact_id
        artifact_result["storage_id"] = result.storage_id
        check_message = "Artifact rendered successfully"

    except Exception as exc:  # pylint: disable=broad-except
        conclusion = ValidatorConclusion.FAILURE.value
        artifact.status.value = "Error"
        severity = "critical"
        check_message += f": {str(exc)}"
        await artifact.save()

    check = None
    check_name = f"{message.artifact_name}: {message.target_name}"
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
                "origin": message.repository_id,
                "kind": "ArtifactDefinition",
                "validator": message.validator_id,
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

    await set_check_status(message=message, conclusion=conclusion, service=service)

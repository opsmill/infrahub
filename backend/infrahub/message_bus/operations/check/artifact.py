from infrahub import lock
from infrahub.core.constants import ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.check import set_check_status

log = get_logger()


async def create(message: messages.CheckArtifactCreate, service: InfrahubServices):
    log.debug("Creating artifact", message=message)
    validator = await service.client.get(kind="CoreArtifactValidator", id=message.validator_id, include=["checks"])

    repo = await InfrahubRepository.init(id=message.repository_id, name=message.repository_name, client=service.client)
    if message.artifact_id:
        artifact = await service.client.get(kind="CoreArtifact", id=message.artifact_id, branch=message.branch_name)
    else:
        async with lock.registry.get(f"{message.target_id}-{message.artifact_definition}", namespace="artifact"):
            artifact = await service.client.create(
                kind="CoreArtifact",
                branch=message.branch_name,
                data={
                    "name": message.artifact_name,
                    "status": "Pending",
                    "object": message.target_id,
                    "definition": message.artifact_definition,
                    "content_type": message.content_type,
                },
            )
            await artifact.save()

    conclusion = ValidatorConclusion.SUCCESS.value
    severity = "info"
    try:
        result = await repo.render_artifact(artifact=artifact, message=message)
        check_log = f"Artifact changed={result.changed}, checksum={result.checksum}, artifact_id={result.artifact_id}, storage_id={result.storage_id}"
    except Exception as exc:  # pylint: disable=broad-except
        conclusion = ValidatorConclusion.FAILURE.value
        artifact.status.value = "Error"
        severity = "critical"
        check_log = str(exc)
        await artifact.save()

    check = None
    check_name = f"{message.artifact_name}: {message.target_name}"
    for relationship in validator.checks.peers:
        existing_check = relationship.peer
        if (
            existing_check.typename == "CoreStandardCheck"
            and existing_check.kind.value == "CheckDefinition"
            and existing_check.name.value == check_name
        ):
            check = existing_check

    if check:
        check.created_at.value = Timestamp().to_string()
        check.message.value = check_log
        check.conclusion.value = conclusion
        check.severity.value = severity
        await check.save()
    else:
        check = await service.client.create(
            kind="CoreStandardCheck",
            data={
                "name": check_name,
                "origin": message.repository_id,
                "kind": "CheckDefinition",
                "validator": message.validator_id,
                "created_at": Timestamp().to_string(),
                "message": check_log,
                "conclusion": conclusion,
                "severity": severity,
            },
        )
        await check.save()

    await set_check_status(message=message, conclusion=conclusion, service=service)

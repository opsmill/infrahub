from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.artifact import define_artifact

log = get_logger()


async def generate(message: messages.RequestArtifactGenerate, service: InfrahubServices):
    log.debug("Generating artifact", message=message)

    repo = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    artifact = await define_artifact(message=message, service=service)

    try:
        result = await repo.render_artifact(artifact=artifact, message=message)
        log.debug(
            "Generated artifact",
            name=message.artifact_name,
            changed=result.changed,
            checksum=result.checksum,
            artifact_id=result.artifact_id,
            storage_id=result.storage_id,
        )
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Failed to generate artifact", error=exc)
        artifact.status.value = "Error"
        await artifact.save()

from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def generate(message: messages.RequestArtifactDefinitionGenerate, service: InfrahubServices) -> None:
    log.info(
        f"Received request to generate artifacts for artifact_definition={message.artifact_definition} on branch={message.branch}"
    )
    await service.client._post(
        f"{service.client.address}/api/artifact/generate/{message.artifact_definition}?branch={message.branch}",
        payload={},
    )

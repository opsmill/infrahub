from infrahub.core.constants import InfrahubKind
from infrahub.log import get_logger
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices

log = get_logger()


async def generate(message: messages.TriggerArtifactDefinitionGenerate, service: InfrahubServices) -> None:
    artifact_definitions = await service.client.all(
        kind=InfrahubKind.ARTIFACTDEFINITION, branch=message.branch, include=["id"]
    )

    events = [
        messages.RequestArtifactDefinitionGenerate(branch=message.branch, artifact_definition=artifact_definition.id)
        for artifact_definition in artifact_definitions
    ]
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)

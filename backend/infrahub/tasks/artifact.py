from typing import Union

from infrahub_sdk import InfrahubNode

from infrahub import lock
from infrahub.core.constants import InfrahubKind
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def define_artifact(
    message: Union[messages.CheckArtifactCreate, messages.RequestArtifactGenerate], service: InfrahubServices
) -> InfrahubNode:
    if message.artifact_id:
        artifact = await service.client.get(
            kind=InfrahubKind.ARTIFACT, id=message.artifact_id, branch=message.branch_name
        )
    else:
        async with lock.registry.get(f"{message.target_id}-{message.artifact_definition}", namespace="artifact"):
            artifacts = await service.client.filters(
                kind=InfrahubKind.ARTIFACT,
                branch=message.branch_name,
                definition__ids=[message.artifact_definition],
                object__ids=[message.target_id],
            )
            if artifacts:
                artifact = artifacts[0]
            else:
                artifact = await service.client.create(
                    kind=InfrahubKind.ARTIFACT,
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
    return artifact

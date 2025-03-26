from infrahub_sdk.node import InfrahubNode
from prefect import task
from prefect.cache_policies import NONE

from infrahub import lock
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.core.constants import InfrahubKind
from infrahub.git.models import RequestArtifactGenerate
from infrahub.services import InfrahubServices


@task(name="define-artifact", task_run_name="Define Artifact", cache_policy=NONE)  # type: ignore[arg-type]
async def define_artifact(
    model: CheckArtifactCreate | RequestArtifactGenerate, service: InfrahubServices
) -> tuple[InfrahubNode, bool]:
    """Return an artifact together with a flag to indicate if the artifact is created now or already existed."""
    created = False
    if model.artifact_id:
        artifact = await service.client.get(kind=InfrahubKind.ARTIFACT, id=model.artifact_id, branch=model.branch_name)
    else:
        async with lock.registry.get(f"{model.target_id}-{model.artifact_definition}", namespace="artifact"):
            artifacts = await service.client.filters(
                kind=InfrahubKind.ARTIFACT,
                branch=model.branch_name,
                definition__ids=[model.artifact_definition],
                object__ids=[model.target_id],
            )
            if artifacts:
                artifact = artifacts[0]
            else:
                artifact = await service.client.create(
                    kind=InfrahubKind.ARTIFACT,
                    branch=model.branch_name,
                    data={
                        "name": model.artifact_name,
                        "status": "Pending",
                        "object": model.target_id,
                        "definition": model.artifact_definition,
                        "content_type": model.content_type,
                    },
                )
                await artifact.save(request_context=model.context.to_request_context())
                created = True
    return artifact, created

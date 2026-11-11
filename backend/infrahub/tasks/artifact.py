from infrahub_sdk.protocols import CoreArtifact
from prefect import task
from prefect.cache_policies import NONE

from infrahub import lock
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.git.models import RequestArtifactGenerate
from infrahub.workers.dependencies import get_client


@task(name="define-artifact", task_run_name="Define Artifact", cache_policy=NONE)
async def define_artifact(model: CheckArtifactCreate | RequestArtifactGenerate) -> tuple[CoreArtifact, bool]:
    """Return an artifact together with a flag to indicate if the artifact is created now or already existed."""
    client = get_client()
    client.request_context = model.context.to_request_context()
    created = False
    if model.artifact_id:
        artifact = await client.get(kind=CoreArtifact, id=model.artifact_id, branch=model.branch_name)
    else:
        async with lock.registry.get(f"{model.target_id}-{model.artifact_definition}", namespace="artifact"):
            artifacts = await client.filters(
                kind=CoreArtifact,
                branch=model.branch_name,
                definition__ids=[model.artifact_definition],
                object__ids=[model.target_id],
            )
            if artifacts:
                artifact = artifacts[0]
            else:
                artifact = await client.create(
                    kind=CoreArtifact,
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

import httpx
from nornir.core.task import Result, Task


def regenerate_host_artifact(task: Task, artifact: str) -> Result:
    node = task.host.data["InfrahubNode"]
    artifact_node = node._client.get(kind="CoreArtifact", name__value=artifact, object__ids=[node.id])

    headers = node._client.headers
    headers["X-INFRAHUB-KEY"] = f"{node._client.config.api_token}"

    with httpx.Client() as client:
        resp = client.post(
            url=f"{node._client.address}/api/artifact/generate/{artifact_node.definition.id}",
            json={"nodes": [artifact_node.id]},
            headers=headers,
        )
    resp.raise_for_status()

    return Result(host=task.host, failed=False)


def generate_artifacts(task: Task, artifact: str, timeout: int = 10) -> Result:
    node = task.host.data["InfrahubNode"]
    artifact_node = node._client.get(kind="CoreArtifactDefinition", artifact_name__value=artifact)

    headers = node._client.headers
    headers["X-INFRAHUB-KEY"] = f"{node._client.config.api_token}"

    with httpx.Client(timeout=httpx.Timeout(timeout)) as client:
        resp = client.post(url=f"{node._client.address}/api/artifact/generate/{artifact_node.id}", headers=headers)
    resp.raise_for_status()

    return Result(host=task.host, failed=False)


def get_artifact(task: Task, artifact: str) -> Result:
    node = task.host.data["InfrahubNode"]

    artifact_node = node._client.get(kind="CoreArtifact", name__value=artifact, object__ids=[node.id])

    headers = node._client.headers
    headers["X-INFRAHUB-KEY"] = f"{node._client.config.api_token}"

    with httpx.Client() as client:
        resp = client.get(
            url=f"{node._client.address}/api/storage/object/{artifact_node.storage_id.value}",
            headers=headers,
        )
    resp.raise_for_status()

    if artifact_node.content_type.value == "application/json":
        data = resp.json()
    else:
        data = resp.text

    return Result(host=task.host, failed=False, content_type=artifact_node.content_type.value, result=data)

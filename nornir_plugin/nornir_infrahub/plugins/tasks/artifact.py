import httpx

from nornir.core.task import Task, Result


def regenerate_host_artifact(task: Task, artifact: str) -> Result:
    node = task.host.data["InfrahubNode"]
    node.artifacts.fetch()

    found = False
    for rel_node in node.artifacts.peers:
        if rel_node.peer.name.value == artifact:
            found = True
            artifact_id = rel_node.peer.id
            definition_id = rel_node.peer.definition.id

    if not found:
        return Result(
            host=task.host,
            failed=True,
            exception=ValueError(f"Could not find artifact '{artifact}' for host '{task.host.name}'"),
        )

    headers = node._client.headers
    headers["X-INFRAHUB-KEY"] = f"{node._client.config.api_token}"

    with httpx.Client() as client:
        resp = client.post(
            url=f"{node._client.address}/api/artifact/generate/{definition_id}",
            json={"nodes": [artifact_id]},
            headers=headers,
        )
    resp.raise_for_status()

    return Result(host=task.host, failed=False)


def generate_artifact(task: Task, artifact: str, timeout: int = 10) -> Result:
    node = task.host.data["InfrahubNode"]
    artifact_node = node._client.get(kind="CoreArtifactDefinition", artifact_name__value=artifact)

    headers = node._client.headers
    headers["X-INFRAHUB-KEY"] = f"{node._client.config.api_token}"

    with httpx.Client(timeout=httpx.Timeout(10)) as client:
        resp = client.post(url=f"{node._client.address}/api/artifact/generate/{artifact_node.id}", headers=headers)
    resp.raise_for_status()

    return Result(host=task.host, failed=False)


def get_artifact(task: Task, artifact: str) -> Result:
    node = task.host.data["InfrahubNode"]
    node.artifacts.fetch()

    found = False
    for rel_node in node.artifacts.peers:
        if rel_node.peer.name.value == artifact:
            found = True
            storage_id = rel_node.peer.storage_id.value
            content_type = rel_node.peer.content_type.value

    if not found:
        return Result(
            host=task.host,
            failed=True,
            exception=ValueError(f"Could not find artifact '{artifact}' for host '{task.host.name}'"),
        )

    headers = node._client.headers
    headers["X-INFRAHUB-KEY"] = f"{node._client.config.api_token}"

    with httpx.Client() as client:
        resp = client.get(
            url=f"{node._client.address}/api/storage/object/{storage_id}",
            headers=headers,
        )
    resp.raise_for_status()

    if content_type == "application/json":
        data = resp.json()
    else:
        data = resp.text

    return Result(host=task.host, failed=False, content_type=content_type, result=data)

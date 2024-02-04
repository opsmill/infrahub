from functools import partial
from pathlib import Path
from typing import List, Optional

import yaml
from infrahub_sdk import InfrahubClientSync


def load_schema(
    client: InfrahubClientSync, schema: Path, branch: Optional[str] = None, extra_attributes: List[dict] = []
):
    branch = branch or "main"
    data = yaml.safe_load(schema.read_text())
    for attr in extra_attributes:
        data["nodes"][0]["attributes"].append({"name": attr["name"], "kind": attr["kind"]})
    client.schema.validate(data)
    client.schema.load(schemas=[data], branch=branch)


def _stage_node(client: InfrahubClientSync, kind: str, prefix: str, amount: int, attrs: int, offset: int = 0):
    client.schema.get("InfraNode")
    extra_attributes = dict()
    for i in range(attrs):
        extra_attributes[f"test{i}"] = "test data"
    for i in range(offset, offset + amount):
        node = client.create(kind=kind, data={"name": f"{prefix}{i}", **extra_attributes})
        node.save()


stage_infranode = partial(_stage_node, kind="InfraNode", prefix="Node")


def _stage_branch(client: InfrahubClientSync, prefix: str, amount: int, attrs: int, offset: int = 0):
    for i in range(offset, offset + amount):
        client.branch.create(branch_name=f"{prefix}{i}", description="description", data_only=True)

    stage_infranode(client=client, amount=100)


stage_branch = partial(_stage_branch, prefix="Branch")

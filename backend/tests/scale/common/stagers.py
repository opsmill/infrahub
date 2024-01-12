from functools import partial
from pathlib import Path
from typing import Optional

import yaml
from infrahub_sdk import InfrahubClientSync


def load_schema(client: InfrahubClientSync, schema: Path, branch: Optional[str] = None):
    branch = branch or "main"
    data = yaml.safe_load(schema.read_text())
    client.schema.validate(data)
    client.schema.load(schemas=[data], branch=branch)


def _stage_node(client: InfrahubClientSync, kind: str, prefix: str, amount: int, offset: int = 0):
    client.schema.get("InfraNode")
    for i in range(offset, offset + amount):
        node = client.create(kind=kind, data={"name": f"{prefix}{i}"})
        node.save()


stage_infranode = partial(_stage_node, kind="InfraNode", prefix="Node")


def _stage_branch(client: InfrahubClientSync, prefix: str, amount: int, offset: int = 0):
    for i in range(offset, offset + amount):
        client.branch.create(branch_name=f"{prefix}{i}", description="description", data_only=True)

    stage_infranode(client=client, amount=100)


stage_branch = partial(_stage_branch, prefix="Branch")

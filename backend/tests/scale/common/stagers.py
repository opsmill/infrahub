from functools import partial
from pathlib import Path
from typing import List, Optional

import yaml
from infrahub_sdk import InfrahubClientSync

from .config import config
from .utils import prepare_node_attributes


def load_schema(
    client: InfrahubClientSync,
    schema: Path,
    branch: Optional[str] = None,
    extra_attributes: List[dict] = [],
    relationships: List[dict] = [],
):
    branch = branch or "main"
    data = yaml.safe_load(schema.read_text())

    data["nodes"][0]["attributes"] += extra_attributes

    if "relationships" not in data["nodes"][0]:
        data["nodes"][0]["relationships"] = list()
    data["nodes"][0]["relationships"] += relationships

    client.schema.validate(data)
    (loaded, response) = client.schema.load(schemas=[data], branch=branch)
    if not loaded:
        raise ValueError(f"Could not load schema: {response}")


def _stage_node(client: InfrahubClientSync, kind: str, prefix: str, amount: int, offset: int = 0):
    client.schema.get("InfraNode")
    extra_attributes = prepare_node_attributes(client)

    for i in range(offset, offset + amount):
        node = client.create(kind=kind, data={"name": f"{prefix}{i}", **extra_attributes})
        node.save()


stage_infranode = partial(_stage_node, kind="InfraNode", prefix="Node")


def _stage_branch(client: InfrahubClientSync, prefix: str, amount: int, offset: int = 0):
    for i in range(offset, offset + config.node_amount):
        client.branch.create(branch_name=f"{prefix}{i}", description="description", sync_with_git=False)

    stage_infranode(client=client, amount=100)


stage_branch = partial(_stage_branch, prefix="Branch")

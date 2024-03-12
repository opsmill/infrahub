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
    attributes: Optional[List[dict]] = None,
    relationships: Optional[List[dict]] = None,
):
    attributes = attributes or []
    relationships = relationships or []
    branch = branch or "main"
    data = yaml.safe_load(schema.read_text())

    data["nodes"][0]["attributes"] += attributes

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

        for j in range(config.changes_amount):
            node.name.value = f"{prefix}{i}-update{j}"
            node.save()


stage_infranode = partial(_stage_node, kind="InfraNode", prefix="Node")


def _stage_branch(client: InfrahubClientSync, prefix: str, amount: int, offset: int = 0):
    extra_attributes = prepare_node_attributes(client)

    for i in range(offset, offset + config.node_amount):
        branch_name = f"{prefix}{i}"
        client.branch.create(branch_name=branch_name, description="description", sync_with_git=True)
        # Add diff by creating a new node
        node = client.create(kind="InfraNode", branch=branch_name, data={"name": "DiffTestNode", **extra_attributes})
        node.save()

    stage_infranode(client=client, amount=100)


stage_branch = partial(_stage_branch, prefix="Branch")


def _stage_branch_update(client: InfrahubClientSync, prefix: str, amount: int, offset: int = 0):
    # Create node for diff
    extra_attributes = prepare_node_attributes(client)
    node = client.create(kind="InfraNode", data={"name": "DiffTestNode", **extra_attributes})
    node.save()

    for i in range(offset, offset + config.node_amount):
        branch_name = f"{prefix}{i}"
        client.branch.create(branch_name=branch_name, description="description", data_only=True)
        # Apply diff to base node
        node._branch = branch_name
        node.name.value = f"DiffTestNodeBranch{i}"
        node.save()

    stage_infranode(client=client, amount=100)


stage_branch_update = partial(_stage_branch_update, prefix="Branch")


def _stage_branch_diff(client: InfrahubClientSync, prefix: str, amount: int, offset: int = 0):
    extra_attributes = prepare_node_attributes(client)

    branch_name = "DiffTestBranch"
    client.branch.create(branch_name=branch_name, description="description", data_only=True)
    for i in range(offset, offset + config.node_amount):
        # Add diff by creating a new node
        node = client.create(kind="InfraNode", branch=branch_name, data={"name": f"{prefix}{i}", **extra_attributes})
        node.save()

    stage_infranode(client=client, amount=100)


stage_branch_diff = partial(_stage_branch_diff, prefix="Node")

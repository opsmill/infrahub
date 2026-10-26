from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.regeneration.branch_artifacts import BranchArtifactDefinitionFinder
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

BRANCH_NAME = "branch-artifacts"

ARTIFACT_TARGET_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )
    ]
)


async def _create_definition(db: InfrahubDatabase, branch: Branch, transform: Node, name: str) -> tuple[Node, Node]:
    device = await Node.init(db=db, schema="TestNetworkDevice", branch=branch)
    await device.new(db=db, name=f"device-{name}")
    await device.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP, branch=branch)
    await group.new(db=db, name=f"targets-{name}", members=[device])
    await group.save(db=db)
    definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION, branch=branch)
    await definition.new(
        db=db,
        name=name,
        targets=group,
        transformation=transform,
        content_type="text/plain",
        artifact_name=name,
        parameters={"value": {"name": "name__value"}},
    )
    await definition.save(db=db)
    return device, definition


async def _create_artifact(db: InfrahubDatabase, branch: Branch, device: Node, definition: Node) -> Node:
    artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch)
    await artifact.new(
        db=db,
        name="config",
        definition=definition,
        status="Ready",
        object=device,
        storage_id="storage-initial",
        checksum="checksum-initial",
        content_type="text/plain",
    )
    await artifact.save(db=db)
    return artifact


async def _update_artifact(
    db: InfrahubDatabase, branch: Branch, artifact_id: str, checksum: str, storage_id: str
) -> None:
    artifact = await NodeManager.get_one(db=db, branch=branch, id=artifact_id)
    artifact.checksum.value = checksum
    artifact.storage_id.value = storage_id
    await artifact.save(db=db)


@pytest.mark.usefixtures("register_core_models_schema")
async def test_finds_only_definitions_with_an_artifact_rendered_on_the_branch(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """A definition is found when the branch wrote one of its artifacts' checksum, and only then."""
    await load_schema(db=db, schema=ARTIFACT_TARGET_SCHEMA, update_db=True)
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="branch-artifacts-repo", location="https://github.com/test/branch-artifacts.git")
    await repository.save(db=db)
    query = await Node.init(db=db, schema="CoreGraphQLQuery")
    await query.new(db=db, name="device-query", query="query { TestNetworkDevice { edges { node { id } } } }")
    await query.save(db=db)
    transform = await Node.init(db=db, schema="CoreTransformJinja2")
    await transform.new(
        db=db, name="device-render", query=str(query.id), repository=str(repository.id), template_path="device.j2"
    )
    await transform.save(db=db)

    untouched_device, untouched = await _create_definition(db, default_branch, transform, "untouched")
    untouched_artifact = await _create_artifact(db, default_branch, untouched_device, untouched)
    rendered_device, rendered = await _create_definition(db, default_branch, transform, "rendered")
    rendered_artifact = await _create_artifact(db, default_branch, rendered_device, rendered)
    stored_device, stored_again = await _create_definition(db, default_branch, transform, "stored-again")
    stored_artifact = await _create_artifact(db, default_branch, stored_device, stored_again)

    branch = await create_branch(db=db, branch_name=BRANCH_NAME)
    await load_schema(db=db, schema=ARTIFACT_TARGET_SCHEMA, branch_name=BRANCH_NAME, update_db=False)
    created_device, created_on_branch = await _create_definition(db, branch, transform, "created-on-branch")
    await _create_artifact(db, branch, created_device, created_on_branch)

    await _update_artifact(db, default_branch, untouched_artifact.id, "checksum-default-branch", "storage-default")
    await _update_artifact(db, branch, rendered_artifact.id, "checksum-branch", "storage-branch")
    await _update_artifact(db, branch, stored_artifact.id, "checksum-initial", "storage-uploaded-again")

    found = await BranchArtifactDefinitionFinder(db=db).find(branch=branch)

    assert found == {rendered.id, created_on_branch.id}

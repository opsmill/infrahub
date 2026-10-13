from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml
from infrahub_sdk.task.models import TaskFilter

from infrahub.core.constants import InfrahubKind, RepositoryDeliveryFailureCause, RepositoryDeliveryStatus
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.git.repository import InfrahubRepository
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.git.conftest import commit_to_remote_branch, create_gogs_repo, gogs_repo_branch_commit
from tests.integration.git.test_git_live_remote import (
    RETRY_DELIVERY,
    _delivery_state,
    _install_remote_branch_rejection_hook,
    _recorded_commit,
    _remove_remote_branch_rejection_hook,
)

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreArtifact, CoreGeneratorDefinition, CoreRepository
    from infrahub.database import InfrahubDatabase
    from tests.helpers.git import GogsServer

DEVICE_KIND = "TestHeldDevice"
DEVICE_NAME = "dev1"
GROUP_NAME = "held-regeneration-devices"
BRANCH_NAME = "held-regeneration"

HELD_REGENERATION_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="HeldDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="description", kind="Text", optional=True),
                *[
                    AttributeSchema(
                        name=f"{prefix}_summary",
                        kind="Text",
                        read_only=True,
                        optional=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform=f"{prefix}-summary"
                        ),
                    )
                    for prefix in ("x", "y")
                ],
            ],
        )
    ]
)

GENERATOR_RUN = """
mutation RunGenerator($id: String!) {
    CoreGeneratorDefinitionRun(data: {id: $id}, wait_until_completion: true) {
        ok
    }
}
"""

RECOMPUTE = """
mutation Recompute($kind: String!, $attribute: String!) {
    InfrahubRecomputeComputedAttribute(data: {kind: $kind, attribute: $attribute}) {
        ok
    }
}
"""


def _repository_files(prefix: str, version: int) -> dict[str, str]:
    """Return a repository with an artifact definition, a generator definition and a Python transform, at a version.

    Each output names the repository and the version, so it shows which commit produced it.
    """
    repository_config = {
        "queries": [
            {"name": f"{prefix}_device", "file_path": "device.gql"},
            {"name": f"{prefix}_device_by_id", "file_path": "device_by_id.gql"},
        ],
        "jinja2_transforms": [
            {"name": f"{prefix}-template", "query": f"{prefix}_device", "template_path": "device.j2"}
        ],
        "python_transforms": [{"name": f"{prefix}-summary", "class_name": "Summary", "file_path": "summary.py"}],
        "artifact_definitions": [
            {
                "name": f"{prefix}-artifact",
                "artifact_name": f"{prefix}-config",
                "parameters": {"name": "name__value"},
                "content_type": "text/plain",
                "targets": GROUP_NAME,
                "transformation": f"{prefix}-template",
            }
        ],
        "generator_definitions": [
            {
                "name": f"{prefix}-generator",
                "file_path": "tag_generator.py",
                "class_name": "TagGenerator",
                "query": f"{prefix}_device",
                "targets": GROUP_NAME,
                "parameters": {"name": "name__value"},
            }
        ],
    }
    fields = "edges { node { name { value } description { value } } }"
    device = f'data["{DEVICE_KIND}"]["edges"][0]["node"]'
    return {
        ".infrahub.yml": yaml.safe_dump(repository_config),
        "device.gql": f"query {prefix}_device($name: String!) {{ {DEVICE_KIND}(name__value: $name) {{ {fields} }} }}\n",
        "device_by_id.gql": f"query {prefix}_device_by_id($id: ID!) {{ {DEVICE_KIND}(ids: [$id]) {{ {fields} }} }}\n",
        "device.j2": (
            f"{prefix} v{version}: {{{{ data.{DEVICE_KIND}.edges[0].node.name.value }}}} "
            f"{{{{ data.{DEVICE_KIND}.edges[0].node.description.value }}}}"
        ),
        "summary.py": (
            "from infrahub_sdk.transforms import InfrahubTransform\n\n\n"
            "class Summary(InfrahubTransform):\n"
            f'    query = "{prefix}_device_by_id"\n\n'
            "    async def transform(self, data: dict) -> str:\n"
            f"        device = {device}\n"
            f"        return f\"{prefix} v{version} {{device['name']['value']}} {{device['description']['value']}}\"\n"
        ),
        "tag_generator.py": (
            "from infrahub_sdk.generator import InfrahubGenerator\n\n\n"
            "class TagGenerator(InfrahubGenerator):\n"
            "    async def generate(self, data: dict) -> None:\n"
            f"        device = {device}\n"
            "        tag = await self.client.create(\n"
            '            kind="BuiltinTag",\n'
            "            data={\n"
            f"                \"name\": f\"{prefix}-{{device['name']['value']}}\",\n"
            f"                \"description\": f\"{prefix} v{version} {{device['description']['value']}}\",\n"
            "            },\n"
            "        )\n"
            "        await tag.save(allow_upsert=True)\n"
        ),
    }


@dataclass(frozen=True)
class OwnedRepository:
    name: str
    node_id: str
    trunk_commit: str


@dataclass(frozen=True)
class Outputs:
    """What a person reads on the default branch for the definitions of one repository."""

    artifact: str
    artifact_checksum: str | None
    tag: str | None
    summary: str | None


@dataclass(frozen=True)
class Runs:
    """How many runs of each regeneration of one repository the task list shows on the default branch."""

    artifact: int
    generator: int
    summary: int


async def _outputs(db: InfrahubDatabase, client: InfrahubClient, prefix: str) -> Outputs:
    artifacts: list[CoreArtifact] = await NodeManager.query(
        db=db, schema=InfrahubKind.ARTIFACT, filters={"definition__name__value": f"{prefix}-artifact"}
    )
    tags = await NodeManager.query(db=db, schema=InfrahubKind.TAG, filters={"name__value": f"{prefix}-{DEVICE_NAME}"})
    devices = await NodeManager.query(db=db, schema=DEVICE_KIND, filters={"name__value": DEVICE_NAME})
    assert (len(artifacts), len(tags), len(devices)) == (1, 1, 1)
    return Outputs(
        artifact=await client.object_store.get(identifier=str(artifacts[0].storage_id.value)),
        artifact_checksum=artifacts[0].checksum.value,
        tag=tags[0].description.value,
        summary={"x": devices[0].x_summary.value, "y": devices[0].y_summary.value}[prefix],
    )


async def _runs(client: InfrahubClient) -> dict[str, Runs]:
    tasks = await client.task.filter(
        filter=TaskFilter(
            branch=registry.default_branch,
            workflow=["artifact-generate", "generator-run", "computed_attribute_process_transform"],
        )
    )
    titles = [task.title for task in tasks]
    return {
        prefix: Runs(
            artifact=titles.count(f"Generate artifact {prefix}-config"),
            generator=titles.count(f"Run generator {prefix}-generator"),
            summary=titles.count(f"Process computed attribute for {DEVICE_KIND}.{prefix}_summary"),
        )
        for prefix in ("x", "y")
    }


async def _all_outputs(db: InfrahubDatabase, client: InfrahubClient) -> dict[str, Outputs]:
    return {prefix: await _outputs(db=db, client=client, prefix=prefix) for prefix in ("x", "y")}


class TestHeldRegenerationLive(TestInfrahubApp):
    async def _add_repository(
        self, db: InfrahubDatabase, client: InfrahubClient, gogs_server: GogsServer, prefix: str
    ) -> OwnedRepository:
        """Add a repository whose definitions are at their first version, and run each definition once."""
        name = f"held-regeneration-{prefix}"
        location = create_gogs_repo(gogs_server.base_url, gogs_server.token, name, gogs_server.container)
        trunk_commit = commit_to_remote_branch(
            gogs_server.container, name, branch="main", files=_repository_files(prefix=prefix, version=1)
        )
        node = await client.create(kind=InfrahubKind.REPOSITORY, data={"name": name, "location": location})
        await node.save()

        generators: list[CoreGeneratorDefinition] = await NodeManager.query(
            db=db, schema=InfrahubKind.GENERATORDEFINITION, filters={"name__value": f"{prefix}-generator"}
        )
        await client.execute_graphql(query=GENERATOR_RUN, variables={"id": generators[0].id})
        await client.execute_graphql(query=RECOMPUTE, variables={"kind": DEVICE_KIND, "attribute": f"{prefix}_summary"})
        return OwnedRepository(name=name, node_id=node.id, trunk_commit=trunk_commit)

    async def test_a_refused_push_holds_the_regeneration_of_its_repository_until_the_retry_delivers_it(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        client: InfrahubClient,
        gogs_server: GogsServer,
    ) -> None:
        """One merge regenerates the other repository at once, and the refused repository once after its delivery."""
        await load_schema(db=db, schema=HELD_REGENERATION_SCHEMA, update_db=True)
        device = await Node.init(db=db, schema=DEVICE_KIND)
        await device.new(db=db, name=DEVICE_NAME, description="first")
        await device.save(db=db)
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name=GROUP_NAME, members=[device])
        await group.save(db=db)
        x = await self._add_repository(db=db, client=client, gogs_server=gogs_server, prefix="x")
        y = await self._add_repository(db=db, client=client, gogs_server=gogs_server, prefix="y")
        initial = {
            "x": Outputs(
                artifact="x v1: dev1 first",
                artifact_checksum="b3a0395102657e5912ad565c66216ddd",
                tag="x v1 first",
                summary="x v1 dev1 first",
            ),
            "y": Outputs(
                artifact="y v1: dev1 first",
                artifact_checksum="31a5c7f1e471fb3451b63e2330d90235",
                tag="y v1 first",
                summary="y v1 dev1 first",
            ),
        }
        assert await _all_outputs(db=db, client=client) == initial

        # The branch changes the device that every definition reads, and every file of the definitions of X.
        await client.branch.create(branch_name=BRANCH_NAME, sync_with_git=True)
        source_commit = commit_to_remote_branch(
            gogs_server.container, x.name, branch=BRANCH_NAME, files=_repository_files(prefix="x", version=2)
        )
        repo = await InfrahubRepository.init(
            id=x.node_id, name=x.name, client=client, infrahub_branch_name=registry.default_branch
        )
        await repo.fetch()
        await repo.pull(branch_name=BRANCH_NAME)
        on_branch: CoreRepository = await NodeManager.get_one(
            db=db, id=x.node_id, kind=InfrahubKind.REPOSITORY, branch=BRANCH_NAME, raise_on_error=True
        )
        assert on_branch.commit.value == source_commit
        changed = await client.get(kind=DEVICE_KIND, name__value=DEVICE_NAME, branch=BRANCH_NAME)
        changed.description.value = "second"
        await changed.save()

        assert await _all_outputs(db=db, client=client) == initial
        assert await _runs(client=client) == {
            "x": Runs(artifact=1, generator=1, summary=1),
            "y": Runs(artifact=1, generator=1, summary=1),
        }
        _install_remote_branch_rejection_hook(container=gogs_server.container, repo_name=x.name)
        try:
            await client.branch.merge(branch_name=BRANCH_NAME)

            regenerated_y = Outputs(
                artifact="y v1: dev1 second",
                artifact_checksum="4a8d17b9e49df18c96251f655db3f716",
                tag="y v1 second",
                summary="y v1 dev1 second",
            )
            assert await _all_outputs(db=db, client=client) == {"x": initial["x"], "y": regenerated_y}
            assert await _runs(client=client) == {
                "x": Runs(artifact=1, generator=1, summary=1),
                "y": Runs(artifact=2, generator=2, summary=2),
            }
            other = await _delivery_state(db=db, repository_id=y.node_id)
            assert (other.status, other.queue.entries, other.held.is_empty) == (RepositoryDeliveryStatus.NONE, (), True)
            assert await _recorded_commit(db=db, repository_id=y.node_id) == gogs_repo_branch_commit(
                gogs_server.container, y.name, "main"
            )
            refused = await _delivery_state(db=db, repository_id=x.node_id)
            assert (refused.status, refused.cause, refused.error) == (
                RepositoryDeliveryStatus.ACTION_REQUIRED,
                RepositoryDeliveryFailureCause.PERMISSION,
                "remote: branch main is protected\n"
                f"Unable to push the branch main to the remote for repository {x.name}: "
                "the remote refused the update (for example missing push permission or branch protection): "
                "[remote rejected] (pre-receive hook declined)",
            )
            assert [
                (entry.source_branch, entry.source_git_branch, entry.source_commit) for entry in refused.queue.entries
            ] == [(BRANCH_NAME, BRANCH_NAME, source_commit)]
            artifact_definitions = await NodeManager.query(
                db=db, schema=InfrahubKind.ARTIFACTDEFINITION, filters={"name__value": "x-artifact"}
            )
            generator_definitions = await NodeManager.query(
                db=db, schema=InfrahubKind.GENERATORDEFINITION, filters={"name__value": "x-generator"}
            )
            assert (
                [item.id for item in refused.held.artifact_definitions],
                [item.id for item in refused.held.generator_definitions],
                [(item.kind, item.attribute) for item in refused.held.python_attributes],
                refused.held.widen,
            ) == (
                [artifact_definitions[0].id],
                [generator_definitions[0].id],
                [(DEVICE_KIND, "x_summary")],
                None,
            )
            assert await _recorded_commit(db=db, repository_id=x.node_id) == x.trunk_commit

            _remove_remote_branch_rejection_hook(container=gogs_server.container, repo_name=x.name)
            await client.execute_graphql(
                query=RETRY_DELIVERY, variables={"id": x.node_id}, branch_name=registry.default_branch
            )
        finally:
            _remove_remote_branch_rejection_hook(container=gogs_server.container, repo_name=x.name)

        assert await _all_outputs(db=db, client=client) == {
            "x": Outputs(
                artifact="x v2: dev1 second",
                artifact_checksum="59a7fc5dcea44c6fad6d65ec4fad9926",
                tag="x v2 second",
                summary="x v2 dev1 second",
            ),
            "y": regenerated_y,
        }
        assert await _runs(client=client) == {
            "x": Runs(artifact=2, generator=2, summary=2),
            "y": Runs(artifact=2, generator=2, summary=2),
        }
        head = gogs_repo_branch_commit(gogs_server.container, x.name, "main")
        delivered = await _delivery_state(db=db, repository_id=x.node_id)
        assert (
            delivered.status,
            delivered.cause,
            delivered.error,
            delivered.queue.entries,
            delivered.held.artifact_definitions,
            delivered.held.generator_definitions,
            delivered.held.python_attributes,
            delivered.held.widen,
            delivered.held.release_leases,
            delivered.last_delivered_commit,
        ) == (RepositoryDeliveryStatus.NONE, None, None, (), (), (), (), None, (), head)
        assert await _recorded_commit(db=db, repository_id=x.node_id) == head

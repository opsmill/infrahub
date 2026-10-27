from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.schema import load_schema

from .artifact_recheck_harness import ArtifactPipeline, ArtifactRecheckTestBase
from .conftest import QUERY_UNIQUE_TARGETS

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

DEVICE_DEFINITION = "device-recheck"
PERSON_DEFINITION = "person-recheck"
DEVICE_SCENARIOS = ("rebase", "settle", "partial", "default-render", "failed", "rebuilt", "rebase-brings-change")

DEVICE_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
        )
    ]
)

PERSON_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="RecheckPerson",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="cars",
                    peer="TestRecheckCar",
                    identifier="recheck__person__car",
                    cardinality=RelationshipCardinality.MANY,
                    kind=RelationshipKind.GENERIC,
                    optional=True,
                )
            ],
        ),
        NodeSchema(
            name="RecheckCar",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="owner",
                    peer="TestRecheckPerson",
                    identifier="recheck__person__car",
                    cardinality=RelationshipCardinality.ONE,
                    kind=RelationshipKind.ATTRIBUTE,
                    optional=True,
                )
            ],
        ),
    ]
)

QUERY_PERSON_CARS = """
query GetPersonCars($ids: [ID!]!) {
    TestRecheckPerson(ids: $ids) {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } } } }
            }
        }
    }
}
"""

QUERY_PERSON_FILTERED_CARS = """
query GetPersonFilteredCars($ids: [ID!]!) {
    TestRecheckPerson(ids: $ids) {
        edges {
            node {
                name { value }
                cars(color__value: "red") { edges { node { name { value } } } }
            }
        }
    }
}
"""


async def _create_query_transform(db: InfrahubDatabase, name: str, query_text: str) -> tuple[Node, Node, Node]:
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name=f"{name}-repo", location=f"https://github.com/test/{name}.git")
    await repository.save(db=db)
    query = await Node.init(db=db, schema="CoreGraphQLQuery")
    await query.new(db=db, name=f"{name}-query", query=query_text)
    await query.save(db=db)
    transform = await Node.init(db=db, schema="CoreTransformJinja2")
    await transform.new(
        db=db, name=f"{name}-render", query=str(query.id), repository=str(repository.id), template_path="t.j2"
    )
    await transform.save(db=db)
    return repository, query, transform


async def _create_artifact(
    db: InfrahubDatabase, branch: Branch, definition: Node, query: Node, target: Node, checksum: str
) -> Node:
    artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=branch)
    await artifact.new(
        db=db,
        name="config",
        definition=definition,
        status="Ready",
        object=target,
        storage_id=f"storage-{checksum}",
        checksum=checksum,
        content_type="text/plain",
    )
    await artifact.save(db=db)
    query_group = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=branch)
    await query_group.new(db=db, name=f"qg-{target.id}", query=str(query.id), members=[target], subscribers=[artifact])
    await query_group.save(db=db)
    return artifact


async def _rebuild_branch_diff(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> None:
    diff_repository = await get_component_registry().get_component(DiffRepository, db=db, branch=default_branch)
    coordinator = await get_component_registry().get_component(DiffCoordinator, db=db, branch=branch)
    for root in await diff_repository.get_roots_metadata(diff_branch_names=[branch.name]):
        if root.base_branch_name != root.diff_branch_name:
            await coordinator.recalculate(base_branch=default_branch, diff_branch=branch, diff_id=root.uuid)


class TestArtifactRecheckDevices(ArtifactRecheckTestBase):
    """An artifact rendered on the branch is checked again when its query returns other data than it was rendered from.

    Each scenario has its own device, with an artifact rendered on the default branch from ``blue``, and its own
    branch and proposed change.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch) -> dict[str, Any]:
        await load_schema(db=db, schema=DEVICE_SCHEMA, update_db=True)
        repository, query, transform = await _create_query_transform(db, "device", QUERY_UNIQUE_TARGETS)

        devices: dict[str, Node] = {}
        for scenario in DEVICE_SCENARIOS:
            device = await Node.init(db=db, schema="TestNetworkDevice")
            await device.new(db=db, name=f"dev-{scenario}", color="blue", description="initial")
            await device.save(db=db)
            devices[scenario] = device

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="recheck-devices", members=list(devices.values()))
        await group.save(db=db)
        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name=DEVICE_DEFINITION,
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"ids": "id"}},
        )
        await definition.save(db=db)

        artifact_ids = {
            scenario: (
                await _create_artifact(db, default_branch, definition, query, device, f"{scenario}-from-blue")
            ).id
            for scenario, device in devices.items()
        }

        branches: dict[str, Branch] = {}
        proposed_change_ids: dict[str, str] = {}
        for scenario in DEVICE_SCENARIOS:
            branch_name = f"feature/recheck-{scenario}"
            branches[scenario] = await create_branch(branch_name=branch_name, db=db)
            await load_schema(db=db, schema=DEVICE_SCHEMA, branch_name=branch_name, update_db=False)
            proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
            await proposed_change.new(
                db=db, name=f"pc-{scenario}", source_branch=branch_name, destination_branch=default_branch.name
            )
            await proposed_change.save(db=db)
            proposed_change_ids[scenario] = proposed_change.id

        return {
            "repository_id": repository.id,
            "query_id": query.id,
            "device_ids": {scenario: device.id for scenario, device in devices.items()},
            "artifact_ids": artifact_ids,
            "branches": branches,
            "proposed_change_ids": proposed_change_ids,
        }

    async def _set_device(
        self, db: InfrahubDatabase, dataset: dict[str, Any], scenario: str, color: str, description: str = "initial"
    ) -> None:
        device = await NodeManager.get_one(
            db=db, branch=dataset["branches"][scenario], id=dataset["device_ids"][scenario]
        )
        device.color.value = color
        device.description.value = description
        await device.save(db=db)

    async def _run(self, pipeline: ArtifactPipeline, dataset: dict[str, Any], scenario: str) -> tuple[list, list]:
        return await pipeline.run_checks(
            branch=dataset["branches"][scenario], proposed_change_id=dataset["proposed_change_ids"][scenario]
        )

    async def _record(
        self, pipeline: ArtifactPipeline, dataset: dict[str, Any], scenario: str, checksum: str, failed: bool = False
    ) -> None:
        await pipeline.record_render(
            branch=dataset["branches"][scenario],
            artifact_id=dataset["artifact_ids"][scenario],
            query_id=dataset["query_id"],
            variables={"ids": dataset["device_ids"][scenario]},
            checksum=checksum,
            failed=failed,
        )

    async def test_value_changed_back_before_a_rebase_is_checked_once_after_the_rebase(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """A rebase drops a changed-back value from the diff, and the artifact rendered before it is checked once."""
        device_id = dataset["device_ids"]["rebase"]
        await self._set_device(db, dataset, "rebase", color="red")
        assert await self._run(pipeline, dataset, "rebase") == ([DEVICE_DEFINITION], [device_id])
        await self._record(pipeline, dataset, "rebase", checksum="rebase-from-red")

        await self._set_device(db, dataset, "rebase", color="blue")
        branch = dataset["branches"]["rebase"]
        await branch.rebase(db=db)
        await _rebuild_branch_diff(db, default_branch, branch)

        assert await self._run(pipeline, dataset, "rebase") == ([DEVICE_DEFINITION], [device_id])
        await self._record(pipeline, dataset, "rebase", checksum="rebase-from-blue-after-rebase")

        assert await self._run(pipeline, dataset, "rebase") == ([DEVICE_DEFINITION], [])

    async def test_artifact_rendered_from_the_current_data_is_not_checked_again(
        self, db: InfrahubDatabase, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """An artifact whose content never matches the default branch's is not rendered on every run."""
        device_id = dataset["device_ids"]["settle"]
        await self._set_device(db, dataset, "settle", color="red")
        assert await self._run(pipeline, dataset, "settle") == ([DEVICE_DEFINITION], [device_id])
        await self._record(pipeline, dataset, "settle", checksum="settle-from-red")

        await self._set_device(db, dataset, "settle", color="blue")
        assert await self._run(pipeline, dataset, "settle") == ([DEVICE_DEFINITION], [device_id])
        await self._record(pipeline, dataset, "settle", checksum="settle-from-blue-with-render-time")

        assert await self._run(pipeline, dataset, "settle") == ([DEVICE_DEFINITION], [])

    async def test_value_changed_back_on_a_node_with_another_change_is_checked(
        self, db: InfrahubDatabase, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """A changed-back field is checked even when an unread field of the same node keeps it in the diff."""
        device_id = dataset["device_ids"]["partial"]
        await self._set_device(db, dataset, "partial", color="red")
        assert await self._run(pipeline, dataset, "partial") == ([DEVICE_DEFINITION], [device_id])
        await self._record(pipeline, dataset, "partial", checksum="partial-from-red")

        await self._set_device(db, dataset, "partial", color="blue", description="edited")

        assert await self._run(pipeline, dataset, "partial") == ([DEVICE_DEFINITION], [device_id])

    async def test_artifact_rendered_again_on_the_default_branch_is_not_checked(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """An artifact the branch never rendered is not checked because the default branch rendered it again."""
        artifact = await NodeManager.get_one(db=db, branch=default_branch, id=dataset["artifact_ids"]["default-render"])
        artifact.checksum.value = "default-render-rendered-again"
        await artifact.save(db=db)
        # An edit to a field the query does not read makes the checks look at the definition's targets.
        await self._set_device(db, dataset, "default-render", color="blue", description="edited")

        assert await self._run(pipeline, dataset, "default-render") == ([DEVICE_DEFINITION], [])

    async def test_artifact_whose_rendering_failed_is_checked_again(
        self, db: InfrahubDatabase, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """An artifact whose last rendering failed is rendered again, though nothing it reads changed since."""
        await self._set_device(db, dataset, "failed", color="blue", description="edited")
        assert await self._run(pipeline, dataset, "failed") == ([DEVICE_DEFINITION], [])
        await self._record(pipeline, dataset, "failed", checksum="unused", failed=True)

        assert await self._run(pipeline, dataset, "failed") == (
            [DEVICE_DEFINITION],
            [dataset["device_ids"]["failed"]],
        )

    async def test_value_changed_back_before_the_diff_is_rebuilt_is_checked(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """A changed-back value that a rebuilt diff no longer lists still selects the definition and its artifact."""
        device_id = dataset["device_ids"]["rebuilt"]
        await self._set_device(db, dataset, "rebuilt", color="red")
        assert await self._run(pipeline, dataset, "rebuilt") == ([DEVICE_DEFINITION], [device_id])
        await self._record(pipeline, dataset, "rebuilt", checksum="rebuilt-from-red")

        await self._set_device(db, dataset, "rebuilt", color="blue")
        await _rebuild_branch_diff(db, default_branch, dataset["branches"]["rebuilt"])

        assert await self._run(pipeline, dataset, "rebuilt") == ([DEVICE_DEFINITION], [device_id])

    async def test_artifact_checked_before_a_rebase_that_brings_a_change_is_checked_again(
        self, db: InfrahubDatabase, default_branch: Branch, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """A rebase can bring default-branch changes to the data of an artifact rendered on the branch."""
        scenario = "rebase-brings-change"
        await self._set_device(db, dataset, scenario, color="blue", description="edited")
        assert await self._run(pipeline, dataset, scenario) == ([DEVICE_DEFINITION], [])
        await self._record(pipeline, dataset, scenario, checksum="rendered-on-branch")

        device = await NodeManager.get_one(db=db, branch=default_branch, id=dataset["device_ids"][scenario])
        device.color.value = "green"
        await device.save(db=db)
        branch = dataset["branches"][scenario]
        await branch.rebase(db=db)
        await _rebuild_branch_diff(db, default_branch, branch)

        assert await self._run(pipeline, dataset, scenario) == ([DEVICE_DEFINITION], [dataset["device_ids"][scenario]])


class TestArtifactRecheckRelationships(ArtifactRecheckTestBase):
    """A person that gained and then lost a car on the branch is checked again, though the diff drops it."""

    query_text = QUERY_PERSON_CARS
    prefix = "persons"

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch) -> dict[str, Any]:
        await load_schema(db=db, schema=PERSON_SCHEMA, update_db=True)
        repository, query, transform = await _create_query_transform(db, self.prefix, self.query_text)

        john = await Node.init(db=db, schema="TestRecheckPerson")
        await john.new(db=db, name=f"{self.prefix}-john")
        await john.save(db=db)
        jane = await Node.init(db=db, schema="TestRecheckPerson")
        await jane.new(db=db, name=f"{self.prefix}-jane")
        await jane.save(db=db)
        car = await Node.init(db=db, schema="TestRecheckCar")
        await car.new(db=db, name=f"car-{self.prefix}", color="red", owner=john)
        await car.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name=f"recheck-{self.prefix}", members=[john, jane])
        await group.save(db=db)
        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name=f"{PERSON_DEFINITION}-{self.prefix}",
            targets=group,
            transformation=transform,
            content_type="text/plain",
            artifact_name="person-config",
            parameters={"value": {"ids": "id"}},
        )
        await definition.save(db=db)
        john_artifact = await _create_artifact(db, default_branch, definition, query, john, "john-with-car")

        branch_name = f"feature/recheck-{self.prefix}"
        branch = await create_branch(branch_name=branch_name, db=db)
        await load_schema(db=db, schema=PERSON_SCHEMA, branch_name=branch_name, update_db=False)
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name=f"pc-{self.prefix}", source_branch=branch_name, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)

        return {
            "repository_id": repository.id,
            "definition_id": definition.id,
            "query": query,
            "definition": definition,
            "john": john,
            "jane": jane,
            "car_id": car.id,
            "john_artifact_id": john_artifact.id,
            "branch": branch,
            "proposed_change_id": proposed_change.id,
        }

    async def _set_owner(self, db: InfrahubDatabase, dataset: dict[str, Any], owner: Node) -> None:
        car = await NodeManager.get_one(db=db, branch=dataset["branch"], id=dataset["car_id"])
        await car.owner.update(db=db, data=owner)
        await car.save(db=db)

    async def test_peer_that_gained_and_lost_a_relationship_is_checked_again(
        self, db: InfrahubDatabase, dataset: dict[str, Any], pipeline: ArtifactPipeline
    ) -> None:
        """The artifact first rendered on the branch for the person who briefly owned the car is checked again."""
        branch = dataset["branch"]
        john = dataset["john"]
        jane = dataset["jane"]
        definition_name = f"{PERSON_DEFINITION}-{self.prefix}"
        both = sorted([john.id, jane.id])

        await self._set_owner(db, dataset, jane)
        assert await pipeline.run_checks(branch=branch, proposed_change_id=dataset["proposed_change_id"]) == (
            [definition_name],
            both,
        )
        await pipeline.record_render(
            branch=branch,
            artifact_id=dataset["john_artifact_id"],
            query_id=dataset["query"].id,
            variables={"ids": john.id},
            checksum="john-without-car",
        )
        jane_artifact = await _create_artifact(
            db, branch, dataset["definition"], dataset["query"], jane, "jane-with-car"
        )
        await pipeline.record_render(
            branch=branch,
            artifact_id=jane_artifact.id,
            query_id=dataset["query"].id,
            variables={"ids": jane.id},
            checksum="jane-with-car",
        )

        await self._set_owner(db, dataset, john)

        assert await pipeline.run_checks(branch=branch, proposed_change_id=dataset["proposed_change_id"]) == (
            [definition_name],
            both,
        )


class TestArtifactRecheckFilteredRelationships(TestArtifactRecheckRelationships):
    """The same holds when the query reads the cars through a filter the car no longer passes for its owner."""

    query_text = QUERY_PERSON_FILTERED_CARS
    prefix = "filtered"

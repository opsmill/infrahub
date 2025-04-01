import asyncio
from pathlib import Path

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.protocols import CoreArtifact, CoreGenericRepository, CoreProposedChange
from infrahub_sdk.schema import NodeSchema, SchemaRoot
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo
from infrahub_sdk.testing.schemas.car_person import (
    TESTING_PERSON,
    SchemaCarPerson,
)

from infrahub.core.constants import ArtifactStatus, InfrahubKind
from tests.helpers.fixtures import get_fixtures_dir

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


async def wait_for_artifact_to_be_ready(
    client: InfrahubClient, interval: int = 3, retries: int = 5
) -> list[CoreArtifact]:
    for _ in range(retries):
        artifacts = await client.all(kind=CoreArtifact)

        artifact_statuses = [artifact.status.value for artifact in artifacts]

        if all(
            artifact_status in [ArtifactStatus.READY.value, ArtifactStatus.ERROR.value]
            for artifact_status in artifact_statuses
        ):
            return artifacts
        await asyncio.sleep(interval)

    raise Exception(f"Artifacts are not ready after {retries} retries")


class TestProposeChangeRepository(TestInfrahubDockerClient, SchemaCarPerson):
    @pytest.fixture(scope="class")
    def infrahub_version(self) -> str:
        return "local"

    @pytest.fixture(scope="class")
    def schema_person_artifact(self, schema_person_base: NodeSchema) -> NodeSchema:
        person_schema = schema_person_base.model_copy(deep=True)
        person_schema.inherit_from = [InfrahubKind.ARTIFACTTARGET]
        return person_schema

    @pytest.fixture(scope="class")
    def initial_schema(
        self,
        schema_car_base: NodeSchema,
        schema_person_artifact: NodeSchema,
        schema_manufacturer_base: NodeSchema,
    ) -> SchemaRoot:
        return SchemaRoot(
            version="1.0",
            nodes=[schema_person_artifact, schema_car_base, schema_manufacturer_base],
        )

    async def test_load_initial_schema(
        self, default_branch: str, client: InfrahubClient, initial_schema: SchemaRoot
    ) -> None:
        await client.schema.wait_until_converged(branch=default_branch)

        resp = await client.schema.load(
            schemas=[initial_schema.to_schema_dict()], branch=default_branch, wait_until_converged=True
        )
        assert resp.errors == {}

    async def test_load_initial_data(self, client: InfrahubClient, default_branch: str, remote_repos_dir: Path) -> None:
        data = await self.create_initial_data(client=client, branch=default_branch)
        persons = data[TESTING_PERSON]

        # Create Group People
        group_people = await client.create(
            kind="CoreStandardGroup", name="people", members=[item.id for item in persons]
        )
        await group_people.save()

        # Add repositories
        fixture_dir = get_fixtures_dir()
        repo_name = "car-dealership"
        repo_dir = fixture_dir / "repos" / repo_name / "initial__main"
        repo = GitRepo(name=repo_name, src_directory=repo_dir, dst_directory=remote_repos_dir)
        await repo.add_to_infrahub(client=client)
        in_sync = await repo.wait_for_sync_to_complete(client=client)
        assert in_sync

        repos = await client.all(kind=CoreGenericRepository)
        assert repos

    async def test_validate_artifact(self, client: InfrahubClient) -> None:
        artifacts = await wait_for_artifact_to_be_ready(client=client)
        assert all(artifact.status.value == ArtifactStatus.READY.value for artifact in artifacts)

    async def test_create_propose_change(self, client: InfrahubClient, default_branch: str) -> None:
        branch = await client.branch.create(branch_name="branch2")
        john = client.store.get(key="John Doe", kind=TESTING_PERSON)

        john_branch = await client.get(kind=TESTING_PERSON, id=john.id, branch=branch.name)
        john_branch.description.value = "new description"
        await john_branch.save()

        pc = await client.create(
            kind=CoreProposedChange, name="pc1", source_branch=branch.name, destination_branch=default_branch
        )
        await pc.save()

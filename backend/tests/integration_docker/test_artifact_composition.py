from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreArtifact
from infrahub_sdk.schema import NodeSchema, SchemaRoot
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo
from infrahub_sdk.testing.schemas.car_person import SchemaCarPerson

from infrahub.core.constants import ArtifactStatus, InfrahubKind

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()


async def wait_for_artifacts(
    client: InfrahubClient, expected_name: str | None = None, interval: int = 3, retries: int = 10
) -> list[CoreArtifact]:
    """Poll until all artifacts (or those matching expected_name) reach a terminal state.

    Raises:
        TimeoutError: When artifacts do not reach a terminal state within the retry budget.

    """
    for _ in range(retries):
        artifacts = await client.all(kind=CoreArtifact)

        if expected_name:
            artifacts = [a for a in artifacts if a.name.value == expected_name]

        if artifacts and all(
            a.status.value in (ArtifactStatus.READY.value, ArtifactStatus.ERROR.value) for a in artifacts
        ):
            return artifacts
        await asyncio.sleep(interval)

    raise TimeoutError(f"Artifacts not ready after {retries * interval}s (filter: {expected_name})")


class TestArtifactComposition(TestInfrahubDockerClient, SchemaCarPerson):
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
        self, schema_car_base: NodeSchema, schema_person_artifact: NodeSchema, schema_manufacturer_base: NodeSchema
    ) -> SchemaRoot:
        return SchemaRoot(version="1.0", nodes=[schema_person_artifact, schema_car_base, schema_manufacturer_base])

    @pytest.fixture(scope="class")
    async def initial_dataset(self, client: InfrahubClient, default_branch: str, initial_schema: SchemaRoot) -> None:
        """Load schema and create persons with a target group."""
        await client.schema.wait_until_converged(branch=default_branch)
        resp = await client.schema.load(
            schemas=[initial_schema.to_schema_dict()], branch=default_branch, wait_until_converged=True
        )
        assert resp.errors == {}
        persons = await self.create_persons(client=client, branch=default_branch)
        group = await client.create(kind="CoreStandardGroup", name="people", members=[p.id for p in persons])
        await group.save()

    async def test_add_section_repo(
        self, client: InfrahubClient, remote_repos_dir: Path, initial_dataset: None
    ) -> None:
        repo = GitRepo(
            name="section-config",
            src_directory=CURRENT_DIRECTORY / "test_files/repos/section-config",
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        assert await repo.wait_for_sync_to_complete(client=client, retries=12)

    async def test_section_artifacts(self, client: InfrahubClient) -> None:
        """Section artifacts are generated with the expected content."""
        artifacts = await wait_for_artifacts(client=client, expected_name="person-section")
        assert len(artifacts) == 2
        assert all(a.status.value == ArtifactStatus.READY.value for a in artifacts)

        contents = set()
        for artifact in artifacts:
            content = await client.object_store.get(identifier=artifact.storage_id.value)
            contents.add(content)
        assert contents == {"! Section config for John Doe", "! Section config for Jane Doe"}

    async def test_add_composite_repo(self, client: InfrahubClient, remote_repos_dir: Path) -> None:
        repo = GitRepo(
            name="composite-config",
            src_directory=CURRENT_DIRECTORY / "test_files/repos/composite-config",
            dst_directory=remote_repos_dir,
        )
        await repo.add_to_infrahub(client=client)
        assert await repo.wait_for_sync_to_complete(client=client, retries=12)

    async def test_composite_artifacts(self, client: InfrahubClient) -> None:
        """Composite artifacts inline section content via the artifact_content filter."""
        artifacts = await wait_for_artifacts(client=client, expected_name="person-composite", retries=20)
        assert len(artifacts) == 2
        assert all(a.status.value == ArtifactStatus.READY.value for a in artifacts)

        contents = set()
        for artifact in artifacts:
            content = await client.object_store.get(identifier=artifact.storage_id.value)
            contents.add(content)
        assert contents == {
            "! Composite config for John Doe\n! Section config for John Doe\n! End composite",
            "! Composite config for Jane Doe\n! Section config for Jane Doe\n! End composite",
        }

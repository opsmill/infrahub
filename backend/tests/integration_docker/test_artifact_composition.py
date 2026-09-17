from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from git import Repo
from infrahub_sdk.protocols import CoreArtifact, CoreRepository
from infrahub_sdk.schema import NodeSchema, SchemaRoot
from infrahub_sdk.testing.docker import TestInfrahubDockerClient
from infrahub_sdk.testing.repository import GitRepo
from infrahub_sdk.testing.schemas.car_person import SchemaCarPerson

from infrahub.core.constants import ArtifactStatus, InfrahubKind, RepositoryOperationalStatus

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

CURRENT_DIRECTORY = Path(__file__).parent.resolve()

pytestmark = pytest.mark.shard_a

# Must stay off "main" to cover repositories whose default branch is not the platform one.
SECTION_GIT_DEFAULT_BRANCH = "production"
# The stack's own default branch, read as a literal because this process never builds the registry.
PLATFORM_DEFAULT_BRANCH = "main"
REGENERATED_ARTIFACT_PREFIX = "! Regenerated section config for"
DECOY_ARTIFACT_PREFIX = "! Platform default branch config for"


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


async def wait_for_artifact_contents(
    client: InfrahubClient, expected_name: str, expected: set[str], interval: int = 5, retries: int = 24
) -> set[str]:
    """Poll until the stored artifact contents match, then return them.

    Waits for the periodic repository sync to pick the new commit up and for the regeneration it
    triggers to land, so the budget covers more than one sync cycle.

    Raises:
        TimeoutError: When the contents do not match within the retry budget.

    """
    contents: set[str] = set()
    for _ in range(retries):
        artifacts = await wait_for_artifacts(client=client, expected_name=expected_name)
        contents = set()
        for artifact in artifacts:
            if artifact.storage_id.value:
                contents.add(await client.object_store.get(identifier=artifact.storage_id.value))
        if contents == expected:
            return contents
        await asyncio.sleep(interval)

    raise TimeoutError(f"Artifact contents {contents} did not reach {expected} after {retries * interval}s")


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
        self, client: InfrahubClient, remote_repos_dir: Path, default_branch: str, initial_dataset: None
    ) -> None:
        repo = GitRepo(
            name="section-config",
            src_directory=CURRENT_DIRECTORY / "test_files/repos/section-config",
            dst_directory=remote_repos_dir,
            initial_branch=SECTION_GIT_DEFAULT_BRANCH,
        )
        repository = await client.create(
            kind=CoreRepository,
            name=repo.name,
            location=f"/remote/{repo.name}",
            default_branch=SECTION_GIT_DEFAULT_BRANCH,
        )
        await repository.save()
        assert await repo.wait_for_sync_to_complete(client=client, branch=default_branch, retries=12)

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

        repository = await client.get(kind=CoreRepository, name__value="section-config")
        assert repository.operational_status.value == RepositoryOperationalStatus.ONLINE.value

    async def test_regeneration_on_a_warm_clone_reads_the_configured_default_branch(
        self, client: InfrahubClient, remote_repos_dir: Path
    ) -> None:
        """Regenerating on a worker that already has a clone renders from the configured default branch.

        The remote gains a branch named after the platform default holding a different template, so a
        regeneration that resolves the wrong branch produces output rather than an error. The assertion
        is therefore on the artifact's content, not on the regeneration completing.
        """
        remote_path = remote_repos_dir / "section-config"
        remote = Repo(remote_path)
        template = remote_path / "templates/person_section.j2"

        # A decoy on the branch named after Infrahub's own default branch. It collides with the
        # mapped default branch, so it is never imported and stays a remote-tracking ref -- which is
        # exactly the state a warm clone holds it in.
        remote.git.checkout("-b", PLATFORM_DEFAULT_BRANCH)
        template.write_text(f"{DECOY_ARTIFACT_PREFIX} {{{{ data.TestingPerson.edges[0].node.name.value }}}}\n")
        remote.index.add([str(template)])
        remote.index.commit("Template on the platform default branch")

        remote.git.checkout(SECTION_GIT_DEFAULT_BRANCH)
        template.write_text(f"{REGENERATED_ARTIFACT_PREFIX} {{{{ data.TestingPerson.edges[0].node.name.value }}}}\n")
        remote.index.add([str(template)])
        remote.index.commit("Advance the configured default branch")

        contents = await wait_for_artifact_contents(
            client=client,
            expected_name="person-section",
            expected={
                f"{REGENERATED_ARTIFACT_PREFIX} John Doe",
                f"{REGENERATED_ARTIFACT_PREFIX} Jane Doe",
            },
        )

        assert not any(content.startswith(DECOY_ARTIFACT_PREFIX) for content in contents)

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

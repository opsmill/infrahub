from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.protocols import CoreTransformJinja2

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp
from tests.integration.proposed_change.artifact_regen_harness import ArtifactRegenGateHarness

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

WATCH_REGEN_SOURCE_BRANCH = "feature/artifact-regen-watch"

WATCH_ARTIFACT_SCHEMA = SchemaRoot(
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
            ],
        )
    ]
)


class TestWatchConfigImport(TestInfrahubApp):
    """A transform declaring ``watch.files`` must keep that closure through import.

    ``watch`` is an SDK-config-only field: it drives closure detection but is not a graph
    attribute, so the integrator strips it before the node create/update payload. If that
    exclusion regresses, the unknown key makes schema validation reject the transform and it
    is silently dropped at import. This asserts the transform survives import with the watched
    directory expanded into its stored ``dependencies`` and ``dependencies_complete = True``,
    even though those partials are not referenced from the template source.
    """

    @pytest.fixture(scope="class")
    def git_repo(self, git_sources_dir: Path) -> FileRepo:
        return FileRepo(name="watch-config", sources_directory=git_sources_dir)

    @pytest.fixture(scope="class")
    async def repo(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        git_repo: FileRepo,
        git_repos_dir: Path,
    ) -> InfrahubRepository:
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=git_repo.name,
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(db=db)

        return await InfrahubRepository.new(
            id=obj.id,
            name=git_repo.name,
            location=git_repo.path,
            client=client,
        )

    async def test_watch_declared_transform_imports_with_full_closure(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        repo: InfrahubRepository,
    ) -> None:
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        # Queries must exist before the Jinja2 transforms that reference them are imported.
        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        transforms = {transform.name.value: transform for transform in await client.all(kind=CoreTransformJinja2)}

        # The watch-declared transform is imported, not dropped over the unknown config key.
        assert set(transforms) == {"watched_report"}

        watched = transforms["watched_report"]
        assert watched.dependencies_complete.value is True

        # The watched directory is expanded recursively and unioned with the auto-detected
        # closure (the manifest and the template itself); the partials are present even though
        # nothing in the template references them.
        assert set(watched.dependencies.value) == {
            ".infrahub.yml",
            "templates/report.j2",
            "templates/partials/helper.j2",
            "templates/partials/extra.j2",
        }


class TestWatchConfigRegen(ArtifactRegenGateHarness):
    """A file inside a watch-declared directory drives regeneration through the real gate.

    The watched directory is expanded into the transform's stored closure at import, so editing
    a file under it must select the artifact definition for regeneration even though the template
    source never references that file. An edit outside the closure selects nothing.
    """

    @pytest.fixture(scope="class")
    def git_sources_dir(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        # The import test in this module already builds a ``watch-config`` repository into the
        # session-scoped sources dir; a fresh per-class dir avoids the name collision.
        return tmp_path_factory.mktemp("watch-regen-sources")

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=WATCH_ARTIFACT_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="dev1", color="red")
        await device.save(db=db)

        git_repo = FileRepo(name="watch-config", sources_directory=git_sources_dir)
        repo_node = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await repo_node.new(
            db=db,
            name=git_repo.name,
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await repo_node.save(db=db)

        repo = await InfrahubRepository.new(
            id=repo_node.id,
            name=git_repo.name,
            location=git_repo.path,
            client=client,
        )

        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        transform = await client.get(kind=CoreTransformJinja2, name__value="watched_report")

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-targets", members=[device])
        await group.save(db=db)

        artdef = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef.new(
            db=db,
            name="artifact-watched",
            targets=group,
            transformation=transform.id,
            content_type="text/plain",
            artifact_name="device-watched",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef.save(db=db)

        await create_branch(branch_name=WATCH_REGEN_SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=WATCH_ARTIFACT_SCHEMA, branch_name=WATCH_REGEN_SOURCE_BRANCH, update_db=False)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db,
            name="regen-watch-pc",
            source_branch=WATCH_REGEN_SOURCE_BRANCH,
            destination_branch=default_branch.name,
        )
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo_node.id,
            "repository_name": git_repo.name,
            "source_branch": WATCH_REGEN_SOURCE_BRANCH,
        }

    async def test_watched_file_edit_selects_definition(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """An edit inside the watched directory selects the definition for regeneration."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            files_changed=["templates/partials/helper.j2"],
        )
        assert selected == ["artifact-watched"]

    async def test_unrelated_file_edit_selects_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """An edit outside the transform closure dispatches no regeneration."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            files_changed=["unrelated.txt"],
        )
        assert selected == []

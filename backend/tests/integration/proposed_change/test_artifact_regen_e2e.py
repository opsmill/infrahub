from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.protocols import CoreTransformJinja2, CoreTransformPython

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import load_schema
from tests.integration.proposed_change.artifact_regen_harness import ArtifactRegenGateHarness

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

SOURCE_BRANCH = "feature/artifact-regen-e2e"

ARTIFACT_SCHEMA = SchemaRoot(
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


class TestArtifactRegenE2E(ArtifactRegenGateHarness):
    """The selection gate runs against transform closures the integrator builds from a real worktree.

    Imports two transforms (one Jinja2, one Python) from a real git repository so the stored
    dependency closures are produced by the real closure builder, not hand-set. The scenarios
    then edit real repository files and assert which artifact definition the gate selects,
    proving the integrator-built closure and the changed-file paths line up end to end.
    Predicates driven purely by node diffs (a query modification, a definition repoint) carry
    no closure dependency and are covered by the component-level selection tests.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="dev1", color="red")
        await device.save(db=db)

        git_repo = FileRepo(name="artifact-regen-e2e", sources_directory=git_sources_dir)
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
        await repo.import_python_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        transform_jinja = await client.get(kind=CoreTransformJinja2, name__value="render-jinja")
        transform_python = await client.get(kind=CoreTransformPython, name__value="render-python")

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-targets", members=[device])
        await group.save(db=db)

        artdef_jinja = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_jinja.new(
            db=db,
            name="artifact-jinja",
            targets=group,
            transformation=transform_jinja.id,
            content_type="text/plain",
            artifact_name="device-jinja",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_jinja.save(db=db)

        artdef_python = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_python.new(
            db=db,
            name="artifact-python",
            targets=group,
            transformation=transform_python.id,
            content_type="text/plain",
            artifact_name="device-python",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_python.save(db=db)

        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(db=db, name="regen-e2e-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name)
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo_node.id,
            "repository_name": git_repo.name,
            "source_branch": SOURCE_BRANCH,
            "transform_jinja_id": transform_jinja.id,
            "transform_python_id": transform_python.id,
        }

    async def test_integrator_builds_real_closures(
        self,
        dataset: dict[str, Any],
        client: InfrahubClient,
    ) -> None:
        """Both transforms import with closures built by the real integrator from the worktree."""
        transform_jinja = await client.get(kind=CoreTransformJinja2, id=dataset["transform_jinja_id"])
        transform_python = await client.get(kind=CoreTransformPython, id=dataset["transform_python_id"])

        assert transform_jinja.dependencies_complete.value is True
        assert set(transform_jinja.dependencies.value) == {
            ".infrahub.yml",
            "templates/device.j2",
            "partials/header.j2",
        }

        assert transform_python.dependencies_complete.value is True
        assert set(transform_python.dependencies.value) == {
            ".infrahub.yml",
            "transforms/foo/foo.py",
            "transforms/foo/helpers.py",
            "transforms/foo/__init__.py",
        }

    async def test_readme_edit_regenerates_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A repository edit outside every transform closure dispatches no regeneration."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            files_changed=["README.md"],
        )
        assert selected == []

    async def test_transform_source_edit_selects_only_owning_definition(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Editing a transform's own source file selects only the definition using it."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            files_changed=["transforms/foo/foo.py"],
        )
        assert selected == ["artifact-python"]

    async def test_sibling_helper_edit_selects_via_package_floor(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A sibling file in the transform's package directory selects the owning definition."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            files_changed=["transforms/foo/helpers.py"],
        )
        assert selected == ["artifact-python"]

    async def test_jinja_partial_edit_selects_via_transitive_include(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A transitively included Jinja2 partial selects the definition that renders it."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            files_changed=["partials/header.j2"],
        )
        assert selected == ["artifact-jinja"]

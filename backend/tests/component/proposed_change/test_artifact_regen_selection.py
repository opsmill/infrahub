from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.schema import load_schema

from .conftest import ArtifactRegenTestBase, make_node_diff

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

SOURCE_BRANCH = "feature/artifact-regen-selection"

QUERY_JINJA = """
query GetJinjaDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

QUERY_PYTHON = """
query GetPythonDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } color { value } } }
    }
}
"""

# The closure the integrator would store at import time for each transform. The Jinja2
# closure carries a transitively-included partial; the Python closure carries a sibling
# helper picked up by the package-directory floor. The repository manifest is part of
# every closure.
JINJA_DEPENDENCIES = [".infrahub.yml", "partials/header.j2", "templates/device.j2"]
PYTHON_DEPENDENCIES = [".infrahub.yml", "transforms/foo/foo.py", "transforms/foo/helpers.py"]

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


class TestArtifactRegenSelection(ArtifactRegenTestBase):
    """The selection gate submits a regeneration request only for the definition a change actually affects.

    Drives the ``refresh_artifacts`` flow against two artifact definitions backed by
    distinct queries and transforms (one Jinja2, one Python) sharing a single
    repository. Each scenario asserts the exact set of definitions for which a
    per-definition check is dispatched, proving unrelated repository edits and
    sibling definitions are left untouched.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="dev1", color="red")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="regen-repo", location="https://github.com/test/regen-repo.git")
        await repo.save(db=db)

        query_jinja = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_jinja.new(db=db, name="GetJinjaDevice", query=QUERY_JINJA)
        await query_jinja.save(db=db)

        query_python = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_python.new(db=db, name="GetPythonDevice", query=QUERY_PYTHON)
        await query_python.save(db=db)

        transform_jinja = await Node.init(db=db, schema="CoreTransformJinja2")
        await transform_jinja.new(
            db=db,
            name="render-jinja",
            query=str(query_jinja.id),
            repository=str(repo.id),
            template_path="templates/device.j2",
            dependencies=JINJA_DEPENDENCIES,
            dependencies_complete=True,
        )
        await transform_jinja.save(db=db)

        transform_python = await Node.init(db=db, schema="CoreTransformPython")
        await transform_python.new(
            db=db,
            name="render-python",
            query=str(query_python.id),
            repository=str(repo.id),
            file_path="transforms/foo/foo.py",
            class_name="Foo",
            dependencies=PYTHON_DEPENDENCIES,
            dependencies_complete=True,
        )
        await transform_python.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-targets", members=[device])
        await group.save(db=db)

        artdef_jinja = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_jinja.new(
            db=db,
            name="artifact-jinja",
            targets=group,
            transformation=transform_jinja,
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
            transformation=transform_python,
            content_type="text/plain",
            artifact_name="device-python",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_python.save(db=db)

        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db, name="regen-selection-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "repository_name": "regen-repo",
            "source_branch": SOURCE_BRANCH,
            "query_jinja_id": query_jinja.id,
            "query_python_id": query_python.id,
            "artdef_jinja_id": artdef_jinja.id,
            "artdef_python_id": artdef_python.id,
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
            diff_summary=[],
            files_changed=["README.md"],
        )
        assert selected == []

    async def test_query_edit_selects_only_owning_definition(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A query modification selects the definition bound to that query and no other.

        The edited ``.gql`` file is also present in the repository diff but belongs to
        no transform closure, so it cannot independently select either definition; the
        match comes solely from the query node modification.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_jinja_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
            files_changed=["queries/device.gql"],
        )
        assert selected == ["artifact-jinja"]

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
            diff_summary=[],
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
        """A sibling file in the transform's package directory selects the owning definition.

        The Python closure includes every sibling under the transform's directory, so a
        helper edit that the source file never imports still drives regeneration.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
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
            diff_summary=[],
            files_changed=["partials/header.j2"],
        )
        assert selected == ["artifact-jinja"]

    async def test_definition_repoint_selects_only_that_definition(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A modification to the definition node selects that definition without touching siblings."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[
                make_node_diff(dataset["artdef_jinja_id"], "CoreArtifactDefinition", SOURCE_BRANCH, ["targets"])
            ],
        )
        assert selected == ["artifact-jinja"]

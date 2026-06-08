from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from tests.helpers.schema import load_schema

from .conftest import FLOW_RUN_LOGGER, ArtifactRegenTestBase, make_node_diff

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

SOURCE_BRANCH = "feature/artifact-regen-logging"

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

QUERY_INCOMPLETE = """
query GetIncompleteDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

QUERY_LEGACY = """
query GetLegacyDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

JINJA_DEPENDENCIES = [".infrahub.yml", "partials/header.j2", "templates/device.j2"]
PYTHON_DEPENDENCIES = [".infrahub.yml", "transforms/foo/foo.py", "transforms/foo/helpers.py"]
# The closure the integrator would store for a transform with an unresolved dynamic include:
# a partial list, flagged incomplete so the gate falls back to regenerate-on-any-change.
INCOMPLETE_DEPENDENCIES = [".infrahub.yml", "templates/dynamic.j2"]

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


class TestArtifactRegenLogging(ArtifactRegenTestBase):
    """Every regeneration decision the selection gate makes is explained in the task log.

    Drives ``refresh_artifacts`` against a repository carrying a complete Jinja2
    closure, a complete Python closure, and a deliberately incomplete closure, then
    reads back the flow-run log to confirm each predicate writes the documented
    diagnostic naming the query, file, definition field, or fallback reason that
    triggered it. This is the end-to-end half of the diagnostic contract whose exact
    format strings are pinned by the predicate and closure-builder unit tests.
    """

    @pytest.fixture(autouse=True)
    def propagate_flow_logs(self) -> Generator[None, None, None]:
        logger = logging.getLogger(FLOW_RUN_LOGGER)
        original = logger.propagate
        logger.propagate = True
        yield
        logger.propagate = original

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
        await repo.new(db=db, name="regen-log-repo", location="https://github.com/test/regen-log-repo.git")
        await repo.save(db=db)

        query_jinja = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_jinja.new(db=db, name="GetJinjaDevice", query=QUERY_JINJA)
        await query_jinja.save(db=db)

        query_python = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_python.new(db=db, name="GetPythonDevice", query=QUERY_PYTHON)
        await query_python.save(db=db)

        query_incomplete = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_incomplete.new(db=db, name="GetIncompleteDevice", query=QUERY_INCOMPLETE)
        await query_incomplete.save(db=db)

        query_legacy = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_legacy.new(db=db, name="GetLegacyDevice", query=QUERY_LEGACY)
        await query_legacy.save(db=db)

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

        transform_incomplete = await Node.init(db=db, schema="CoreTransformJinja2")
        await transform_incomplete.new(
            db=db,
            name="render-incomplete",
            query=str(query_incomplete.id),
            repository=str(repo.id),
            template_path="templates/dynamic.j2",
            dependencies=INCOMPLETE_DEPENDENCIES,
            dependencies_complete=False,
        )
        await transform_incomplete.save(db=db)

        # A transform imported before this feature deployed: dependencies and
        # dependencies_complete are left null so the gate uses the legacy fallback.
        transform_legacy = await Node.init(db=db, schema="CoreTransformJinja2")
        await transform_legacy.new(
            db=db,
            name="render-legacy",
            query=str(query_legacy.id),
            repository=str(repo.id),
            template_path="templates/legacy.j2",
        )
        await transform_legacy.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="regen-log-targets", members=[device])
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

        artdef_incomplete = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_incomplete.new(
            db=db,
            name="artifact-incomplete",
            targets=group,
            transformation=transform_incomplete,
            content_type="text/plain",
            artifact_name="device-incomplete",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_incomplete.save(db=db)

        artdef_legacy = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef_legacy.new(
            db=db,
            name="artifact-legacy",
            targets=group,
            transformation=transform_legacy,
            content_type="text/plain",
            artifact_name="device-legacy",
            parameters={"value": {"name": "name__value"}},
        )
        await artdef_legacy.save(db=db)

        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db, name="regen-logging-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "repository_name": "regen-log-repo",
            "source_branch": SOURCE_BRANCH,
            "query_jinja_id": query_jinja.id,
            "artdef_jinja_id": artdef_jinja.id,
        }

    async def test_query_edit_log_names_the_query(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A query modification is explained by naming the query and its id as the cause of regeneration."""
        messages = await self._run_refresh_capturing_log(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            caplog=caplog,
            diff_summary=[make_node_diff(dataset["query_jinja_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
        )
        assert (
            f"Definition artifact-jinja ({dataset['artdef_jinja_id']}): GraphQL query GetJinjaDevice "
            f"({dataset['query_jinja_id']}) was modified - all artifacts of this definition will regenerate."
        ) in messages

    async def test_transform_source_edit_log_names_the_file(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A transform-source edit is explained by naming the changed file inside the transform's dependency closure."""
        messages = await self._run_refresh_capturing_log(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            caplog=caplog,
            diff_summary=[],
            files_changed=["transforms/foo/foo.py"],
        )
        assert (
            "Definition artifact-python: file transforms/foo/foo.py changed and is in this transform's "
            "dependency closure - all artifacts will regenerate."
        ) in messages

    async def test_jinja_partial_edit_log_names_the_partial(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A transitively included partial that changed is named as the cause of regeneration."""
        messages = await self._run_refresh_capturing_log(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            caplog=caplog,
            diff_summary=[],
            files_changed=["partials/header.j2"],
        )
        assert (
            "Definition artifact-jinja: file partials/header.j2 changed and is in this transform's "
            "dependency closure - all artifacts will regenerate."
        ) in messages

    async def test_definition_repoint_log_names_the_field(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A definition relationship repoint names the changed field as the cause of regeneration."""
        messages = await self._run_refresh_capturing_log(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            caplog=caplog,
            diff_summary=[
                make_node_diff(dataset["artdef_jinja_id"], "CoreArtifactDefinition", SOURCE_BRANCH, ["targets"])
            ],
        )
        assert (
            f"Definition artifact-jinja ({dataset['artdef_jinja_id']}): definition node was modified (targets) - "
            f"all artifacts of this definition will regenerate."
        ) in messages

    async def test_incomplete_closure_log_explains_the_fallback(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A transform with an incomplete closure regenerates on any file change and explains why.

        When auto-detection could not fully resolve a transform's dependencies
        (``dependencies_complete=False``), the gate cannot trust the closure and falls
        back to regenerate-on-any-change, logging that reason. The import-time half -
        the per-unresolved-reference log the closure builder emits while walking the
        template - is covered by the Jinja2 closure-builder unit tests, since those
        references are not carried into the pipeline.
        """
        messages = await self._run_refresh_capturing_log(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            caplog=caplog,
            diff_summary=[],
            files_changed=["docs/unrelated.md"],
        )
        assert (
            "Definition artifact-incomplete: transform dependency closure is incomplete "
            "(dependencies_complete=False) - falling back to regenerate-on-any-file-change."
        ) in messages

    async def test_legacy_closure_log_explains_the_self_heal(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A transform imported before this feature carries no closure and regenerates on any file change.

        Such a transform has ``dependencies=null``, so the gate cannot use a precise
        closure and falls back to regenerate-on-any-change. The log states the closure
        will populate on the transform's next natural re-import, making it visible that
        the upgrade is safe without operator intervention.
        """
        messages = await self._run_refresh_capturing_log(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            caplog=caplog,
            diff_summary=[],
            files_changed=["docs/unrelated.md"],
        )
        assert (
            "Definition artifact-legacy: transform was imported before this feature deployed (dependencies=null) - "
            "falling back to regenerate-on-any-file-change. The next re-import of this transform will populate "
            "its dependency closure."
        ) in messages

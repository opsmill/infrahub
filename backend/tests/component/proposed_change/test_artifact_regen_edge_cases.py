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

SOURCE_BRANCH = "feature/artifact-regen-edge-cases"

QUERY = """
query GetDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

ARTIFACT_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            uniqueness_constraints=[["name__value"]],
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )
    ]
)


class TestArtifactRegenEdgeCases(ArtifactRegenTestBase):
    """Boundary behaviors of the selection gate not expressible at the unit level.

    Covers net-empty diffs, whole-repo manifest edits, single-dispatch deduplication,
    shared queries, and source-branch-only definitions.

    Each scenario drives ``refresh_artifacts`` and inspects which definitions are
    dispatched for regeneration, covering cases that the per-predicate unit tests
    cannot express because they depend on the gate iterating over several real
    definitions backed by a shared repository.
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
        await device.new(db=db, name="dev1")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="edge-repo", location="https://github.com/test/edge-repo.git")
        await repo.save(db=db)

        query_solo = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_solo.new(db=db, name="GetDeviceSolo", query=QUERY)
        await query_solo.save(db=db)

        query_shared = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_shared.new(db=db, name="GetDeviceShared", query=QUERY)
        await query_shared.save(db=db)

        query_new = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_new.new(db=db, name="GetDeviceNew", query=QUERY)
        await query_new.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="edge-targets", members=[device])
        await group.save(db=db)

        async def _make_definition(
            *, def_name: str, artifact_name: str, query_id: str, template: str, branch: Branch | None = None
        ) -> Node:
            transform = await Node.init(db=db, schema="CoreTransformJinja2", branch=branch)
            await transform.new(
                db=db,
                name=f"transform-{def_name}",
                query=query_id,
                repository=str(repo.id),
                template_path=template,
                dependencies=[".infrahub.yml", template],
                dependencies_complete=True,
            )
            await transform.save(db=db)

            definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION, branch=branch)
            await definition.new(
                db=db,
                name=def_name,
                targets=group,
                transformation=transform,
                content_type="text/plain",
                artifact_name=artifact_name,
                parameters={"value": {"name": "name__value"}},
            )
            await definition.save(db=db)
            return definition

        artdef_a = await _make_definition(
            def_name="artifact-a", artifact_name="device-a", query_id=str(query_solo.id), template="templates/a.j2"
        )
        artdef_s1 = await _make_definition(
            def_name="artifact-s1", artifact_name="device-s1", query_id=str(query_shared.id), template="templates/s1.j2"
        )
        artdef_s2 = await _make_definition(
            def_name="artifact-s2", artifact_name="device-s2", query_id=str(query_shared.id), template="templates/s2.j2"
        )

        source_branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        # A definition that exists only on the source branch; it has no counterpart on
        # the destination branch, so it surfaces as an "added" node in the diff.
        artdef_new = await _make_definition(
            def_name="artifact-new",
            artifact_name="device-new",
            query_id=str(query_new.id),
            template="templates/new.j2",
            branch=source_branch,
        )

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(db=db, name="regen-edge-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name)
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "repository_name": "edge-repo",
            "source_branch": SOURCE_BRANCH,
            "query_shared_id": query_shared.id,
            "query_solo_id": query_solo.id,
            "artdef_a_id": artdef_a.id,
            "artdef_s1_id": artdef_s1.id,
            "artdef_s2_id": artdef_s2.id,
            "artdef_new_id": artdef_new.id,
        }

    async def test_net_empty_diff_regenerates_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """An edit reverted within the same branch leaves no net change, so nothing regenerates."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=[],
        )
        assert selected == []

    async def test_manifest_edit_regenerates_every_transform_in_repo(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Editing ``.infrahub.yml`` regenerates every transform because it is in each closure.

        The manifest is appended to every transform's dependency list at import time, so
        a manifest change conservatively selects all definitions backed by the repository.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=[".infrahub.yml"],
        )
        assert set(selected) == {"artifact-a", "artifact-s1", "artifact-s2", "artifact-new"}

    async def test_query_and_transform_change_dispatches_definition_once(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A definition whose query and transform both change is dispatched exactly once."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_solo_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
            files_changed=["templates/a.j2"],
        )
        assert selected == ["artifact-a"]

    async def test_shared_query_edit_selects_every_dependent_definition(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A query edit selects every definition whose transform references that query."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_shared_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
        )
        assert set(selected) == {"artifact-s1", "artifact-s2"}

    async def test_source_branch_only_definition_is_selected(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A definition that exists only on the source branch is selected as an added node.

        The gather query reads the source branch, so a source-only definition appears in
        the candidate set and its diff entry carries the ``added`` action that the
        definition predicate fires on.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[
                make_node_diff(
                    dataset["artdef_new_id"], "CoreArtifactDefinition", SOURCE_BRANCH, ["name"], action="ADDED"
                )
            ],
        )
        assert selected == ["artifact-new"]

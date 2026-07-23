"""Selection behaviour of the post-merge regeneration follow-up, asserted on dispatched workflows.

Drives the real ``post_process_branch_merge`` flow against a live graph with a recording workflow
backend, seeding the merge diff summary in the cache exactly as the merge orchestrator would. Each
scenario asserts which regeneration workflows are dispatched (and, where subscribers exist, which
members they carry), never rendered artifact content. Every scenario class builds its own dataset so
graph mutations never leak between tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.protocols import CoreGraphQLQuery, CoreTransformJinja2

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch.tasks import post_process_branch_merge
from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.git import InfrahubRepository
from infrahub.workers.dependencies import build_workflow
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.diff_summary import node_diff
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

SOURCE_BRANCH = "feature/merge-selective-regen"
DIFF_CACHE_KEY = "merge-selective-diff"
DEVICE_KIND = "TestNetworkDevice"
UNRELATED_KIND = "TestUnrelated"
# A computed fingerprint and a complete dependency closure make the definitions trustworthy, so the
# selector narrows by the diff rather than defensively regenerating every definition of the repository.
FINGERPRINT = "fingerprint-computed"
TRANSFORM_DEPENDENCIES = ["templates/device.j2", "queries/device_jinja.gql"]
GENERATOR_DEPENDENCIES = ["generators/device.py"]

SELECTIVE_SCHEMA = SchemaRoot(
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

GENERATOR_QUERY = """
query GetGenDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges {
            node {
                name {
                    value
                }
            }
        }
    }
}
"""


class _MergeSelectiveRegenBase(TestInfrahubApp):
    """Shared fixtures and graph-building blocks for the post-merge selection scenarios.

    Installs a recording workflow backend over the live one, enables the selective feature, and
    disables the post-dispatch diff machinery so a scenario observes only the regeneration workflows
    the follow-up dispatches. Subclasses build the dataset each scenario needs and call
    ``_run_follow_up`` with the diff summary under test.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        workflow_local: Any,
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        # workflow_local scopes build_workflow to the live local backend; depend on it so it runs
        # first, then re-scope to the recorder as the inner (active) provider for the follow-up.
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.reset()

    @pytest.fixture(scope="class", autouse=True)
    def enable_selective(self) -> Generator[None, None, None]:
        original = config.SETTINGS.main.selective_execution_after_merge
        config.SETTINGS.main.selective_execution_after_merge = True
        yield
        config.SETTINGS.main.selective_execution_after_merge = original

    @pytest.fixture(scope="class", autouse=True)
    def disable_diff_update(self) -> Generator[None, None, None]:
        # The follow-up short-circuits after dispatch when this is off, so the scenarios never enter
        # the diff-update machinery that is out of scope here.
        original = config.SETTINGS.main.diff_update_after_merge
        config.SETTINGS.main.diff_update_after_merge = False
        yield
        config.SETTINGS.main.diff_update_after_merge = original

    async def _seed_schema(self, db: InfrahubDatabase) -> None:
        await load_schema(db=db, schema=SELECTIVE_SCHEMA, update_db=True)

    async def _make_device(self, db: InfrahubDatabase, *, name: str, color: str = "red") -> Node:
        device = await Node.init(db=db, schema=DEVICE_KIND)
        await device.new(db=db, name=name, color=color)
        await device.save(db=db)
        return device

    async def _import_transform(
        self, db: InfrahubDatabase, client: InfrahubClient, git_sources_dir: Path
    ) -> tuple[Node, CoreTransformJinja2, CoreGraphQLQuery]:
        # The sources directory is shared across the session, so each scenario class copies the repo
        # into its own subdirectory to avoid colliding on the fixture's destination path.
        sources_dir = git_sources_dir / self.__class__.__name__
        git_repo = FileRepo(name="artifact-regen-e2e", sources_directory=sources_dir)
        repo_node = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await repo_node.new(
            db=db, name=git_repo.name, description="test repository", location="git@github.com:mock/test.git"
        )
        await repo_node.save(db=db)
        repo = await InfrahubRepository.new(id=repo_node.id, name=git_repo.name, location=git_repo.path, client=client)
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file
        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]
        await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        transform = await client.get(kind=CoreTransformJinja2, name__value="render-jinja")
        # A trustworthy, complete dependency closure keeps the transform's artifact definition on the
        # narrowing path rather than the defensive regenerate-everything fallback.
        transform.dependencies.value = TRANSFORM_DEPENDENCIES
        transform.dependencies_complete.value = True
        await transform.save()
        query = await client.get(kind=CoreGraphQLQuery, name__value="GetJinjaDevice")
        return repo_node, transform, query

    async def _make_group(self, db: InfrahubDatabase, *, name: str, members: list[Node]) -> Node:
        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name=name, members=members)
        await group.save(db=db)
        return group

    async def _make_artifact_definition(
        self, db: InfrahubDatabase, *, name: str, group: Node, transform_id: str
    ) -> Node:
        artdef = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artdef.new(
            db=db,
            name=name,
            targets=group,
            transformation=transform_id,
            content_type="text/plain",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
            fingerprint=FINGERPRINT,
        )
        await artdef.save(db=db)
        return artdef

    async def _make_generator(
        self,
        db: InfrahubDatabase,
        *,
        name: str,
        query_name: str,
        group: Node,
        repo_node: Node,
        execute_after_merge: bool = True,
    ) -> Node:
        gen_query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await gen_query.new(db=db, name=query_name, query=GENERATOR_QUERY, models=[DEVICE_KIND])
        await gen_query.save(db=db)

        gendef = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef.new(
            db=db,
            name=name,
            query=gen_query,
            repository=repo_node,
            targets=group,
            file_path="generators/device.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
            convert_query_response=False,
            execute_in_proposed_change=False,
            execute_after_merge=execute_after_merge,
            fingerprint=FINGERPRINT,
            dependencies=GENERATOR_DEPENDENCIES,
            dependencies_complete=True,
        )
        await gendef.save(db=db)
        return gendef

    async def _make_artifact_subscriber(self, db: InfrahubDatabase, *, name: str, device: Node, artdef: Node) -> Node:
        artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
        await artifact.new(
            db=db,
            name=name,
            definition=artdef,
            status="Ready",
            object=device,
            storage_id=f"storage-{name}",
            checksum=f"checksum-{name}",
            content_type="text/plain",
        )
        await artifact.save(db=db)
        return artifact

    async def _make_query_group(
        self, db: InfrahubDatabase, *, name: str, query_id: str, member: Node, subscriber: Node
    ) -> Node:
        query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
        await query_group.new(db=db, name=name, query=query_id, members=[member], subscribers=[subscriber])
        await query_group.save(db=db)
        return query_group

    def _context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    async def _run_follow_up(
        self,
        *,
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        diff_summary: list[NodeDiff],
    ) -> None:
        summary_cache = DiffSummaryCache(
            cache=memory_cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge"
        )
        await summary_cache.set(diff_id=DIFF_CACHE_KEY, diff_summary=diff_summary)
        await post_process_branch_merge(
            source_branch=SOURCE_BRANCH,
            target_branch=default_branch.name,
            context=self._context(admin_account, default_branch),
            merge_diff_cache_key=DIFF_CACHE_KEY,
        )

    @staticmethod
    def _artifact_requests(recorder: WorkflowRecorder) -> list[Any]:
        return [
            call["parameters"]["model"] for call in recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE)
        ]

    @staticmethod
    def _generator_run_models(recorder: WorkflowRecorder) -> list[Any]:
        """Every generator-run request the follow-up dispatched, whether submitted or executed."""
        return [
            call["parameters"]["model"]
            for call in (*recorder.submit_calls, *recorder.execute_calls)
            if call["workflow"] == REQUEST_GENERATOR_DEFINITION_RUN
        ]

    def _device_diff(self, *, target_branch: str, device_id: str, action: str = "UPDATED") -> list[NodeDiff]:
        return [
            node_diff(
                node_id=device_id,
                kind=DEVICE_KIND,
                branch=target_branch,
                action=action,
                display_label="device",
                field_names=["name"],
            )
        ]


class TestIrrelevantKindChange(_MergeSelectiveRegenBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await self._seed_schema(db)
        device = await self._make_device(db, name="dev1")
        repo_node, transform, _ = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device])
        await self._make_artifact_definition(db, name="device-artifact", group=group, transform_id=transform.id)
        await self._make_generator(
            db, name="device-generator", query_name="GetGenDevice", group=group, repo_node=repo_node
        )
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {}

    async def test_irrelevant_kind_change_dispatches_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A merge touching only a kind no definition reads dispatches no regeneration at all."""
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=[
                node_diff(
                    node_id="00000000-0000-0000-0000-0000000000ff",
                    kind=UNRELATED_KIND,
                    branch=default_branch.name,
                    action="UPDATED",
                    display_label="unrelated",
                    field_names=["value"],
                )
            ],
        )
        assert workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_GENERATE) == []
        assert self._generator_run_models(workflow_recorder) == []
        # A regression to the blanket fallback would fire the trigger workflows instead.
        assert workflow_recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE) == []
        assert workflow_recorder.get_submit_calls_for(TRIGGER_GENERATOR_DEFINITION_RUN) == []


class TestRelevantChange(_MergeSelectiveRegenBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await self._seed_schema(db)
        device = await self._make_device(db, name="dev1")
        repo_node, transform, _ = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device])
        await self._make_artifact_definition(db, name="device-artifact", group=group, transform_id=transform.id)
        await self._make_generator(
            db, name="device-generator", query_name="GetGenDevice", group=group, repo_node=repo_node
        )
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {"device_id": device.id}

    async def test_relevant_change_dispatches_matching_definitions(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A relevant change cascades through its after-merge generator to a full artifact regeneration.

        The generator's output lands after the merge diff was captured, so the follow-up regenerates
        every artifact through the blanket trigger rather than the per-definition request the diff alone
        would select.
        """
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=self._device_diff(target_branch=default_branch.name, device_id=dataset["device_id"]),
        )
        generator_models = self._generator_run_models(workflow_recorder)

        assert [model.generator_definition.definition_name for model in generator_models] == ["device-generator"]
        # No existing subscribers, so every live member is new and the filter resolves to "all".
        assert generator_models[0].target_members == []
        # The generator's output lands after the merge diff was captured, so the artifact is regenerated
        # through the blanket trigger rather than a per-definition request the diff alone would select.
        assert self._artifact_requests(workflow_recorder) == []
        trigger_branches = [
            call["parameters"]["branch"]
            for call in workflow_recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)
        ]
        assert trigger_branches == [default_branch.name]


class TestGeneratorExecuteAfterMergeFalse(_MergeSelectiveRegenBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await self._seed_schema(db)
        device = await self._make_device(db, name="dev1")
        repo_node, _, _ = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device])
        await self._make_generator(
            db,
            name="after-merge-generator",
            query_name="GetGenDeviceAfterMerge",
            group=group,
            repo_node=repo_node,
            execute_after_merge=True,
        )
        await self._make_generator(
            db,
            name="skip-after-merge-generator",
            query_name="GetGenDeviceSkip",
            group=group,
            repo_node=repo_node,
            execute_after_merge=False,
        )
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {"device_id": device.id}

    async def test_generator_with_execute_after_merge_false_is_excluded(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Only the generator flagged to run after a merge is dispatched; the opted-out one is absent."""
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=self._device_diff(target_branch=default_branch.name, device_id=dataset["device_id"]),
        )
        dispatched = [
            model.generator_definition.definition_name for model in self._generator_run_models(workflow_recorder)
        ]
        assert dispatched == ["after-merge-generator"]


class TestMemberNarrowing(_MergeSelectiveRegenBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await self._seed_schema(db)
        device1 = await self._make_device(db, name="dev1", color="red")
        device2 = await self._make_device(db, name="dev2", color="blue")
        _repo_node, transform, query = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device1, device2])
        artdef = await self._make_artifact_definition(
            db, name="device-artifact", group=group, transform_id=transform.id
        )
        # Existing subscribers for both members mean neither is treated as new, so the narrowing is
        # driven purely by which member's queried field the diff changed.
        for device in (device1, device2):
            artifact = await self._make_artifact_subscriber(
                db, name=f"artifact-{device.name.value}", device=device, artdef=artdef
            )
            await self._make_query_group(
                db, name=f"qg-{device.name.value}", query_id=query.id, member=device, subscriber=artifact
            )
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {"device1_id": device1.id, "device2_id": device2.id}

    async def test_change_to_one_member_narrows_the_filter(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A change to one member's queried field narrows the request to exactly that member."""
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=self._device_diff(target_branch=default_branch.name, device_id=dataset["device1_id"]),
        )
        artifact_requests = self._artifact_requests(workflow_recorder)
        assert [request.artifact_definition_name for request in artifact_requests] == ["device-artifact"]
        assert artifact_requests[0].members == [dataset["device1_id"]]


class TestMemberDeletion(_MergeSelectiveRegenBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await self._seed_schema(db)
        device1 = await self._make_device(db, name="dev1", color="red")
        device2 = await self._make_device(db, name="dev2", color="blue")
        _repo_node, transform, query = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device1, device2])
        artdef = await self._make_artifact_definition(
            db, name="device-artifact", group=group, transform_id=transform.id
        )
        for device in (device1, device2):
            artifact = await self._make_artifact_subscriber(
                db, name=f"artifact-{device.name.value}", device=device, artdef=artdef
            )
            await self._make_query_group(
                db, name=f"qg-{device.name.value}", query_id=query.id, member=device, subscriber=artifact
            )
        device1_id = device1.id
        # The member is removed on the branch and the deletion applies on merge; the live target group
        # no longer carries it when the follow-up reconciles.
        await device1.delete(db=db)
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {"device1_id": device1_id, "device2_id": device2.id}

    async def test_deleting_a_member_does_not_break_selection(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A deleted member is reconciled away without crashing the follow-up or being dispatched."""
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=self._device_diff(
                target_branch=default_branch.name, device_id=dataset["device1_id"], action="DELETED"
            ),
        )
        for request in self._artifact_requests(workflow_recorder):
            assert dataset["device1_id"] not in request.members


class TestConcurrentlyAddedMember(_MergeSelectiveRegenBase):
    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        git_sources_dir: Path,
        git_repos_dir: Path,
    ) -> dict[str, Any]:
        await self._seed_schema(db)
        device1 = await self._make_device(db, name="dev1", color="red")
        device2 = await self._make_device(db, name="dev2", color="blue")
        device3 = await self._make_device(db, name="dev3", color="green")
        _repo_node, transform, query = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device1, device2, device3])
        artdef = await self._make_artifact_definition(
            db, name="device-artifact", group=group, transform_id=transform.id
        )
        # Only the two long-lived members carry a subscriber; the third models a member that main
        # gained while the branch existed, so it has no artifact yet.
        for device in (device1, device2):
            artifact = await self._make_artifact_subscriber(
                db, name=f"artifact-{device.name.value}", device=device, artdef=artdef
            )
            await self._make_query_group(
                db, name=f"qg-{device.name.value}", query_id=query.id, member=device, subscriber=artifact
            )
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {"device1_id": device1.id, "device2_id": device2.id, "device3_id": device3.id}

    async def test_concurrently_added_member_does_not_misroute_selection(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """The impacted member and the subscriber-less new member regenerate; the untouched one does not."""
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=self._device_diff(target_branch=default_branch.name, device_id=dataset["device1_id"]),
        )
        artifact_requests = self._artifact_requests(workflow_recorder)
        assert [request.artifact_definition_name for request in artifact_requests] == ["device-artifact"]
        # A member added on main without a subscriber is treated as new and regenerates alongside the
        # impacted member, while the untouched existing member is left out.
        assert set(artifact_requests[0].members) == {dataset["device1_id"], dataset["device3_id"]}


class TestAfterMergeGeneratorArtifactCascade(_MergeSelectiveRegenBase):
    """An after-merge generator's output reaches its consuming artifacts.

    The generator runs in the post-merge follow-up, after the merge diff was captured, so the fields
    it writes are absent from that diff. The change under test edits only a device field the artifact
    query never reads, so the artifact is never selected on the diff's own merit -- the sole reason to
    regenerate it is that an after-merge generator ran. The follow-up must therefore regenerate every
    artifact once the generator has run.
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
        await self._seed_schema(db)
        device = await self._make_device(db, name="dev1", color="red")
        repo_node, transform, query = await self._import_transform(db, client, git_sources_dir)
        group = await self._make_group(db, name="regen-targets", members=[device])
        artdef = await self._make_artifact_definition(
            db, name="device-artifact", group=group, transform_id=transform.id
        )
        # An existing subscriber keeps the member off the "new member" path, so a change to a field the
        # artifact query never reads leaves the artifact with nothing to render on the diff's own merit.
        artifact = await self._make_artifact_subscriber(db, name="artifact-dev1", device=device, artdef=artdef)
        await self._make_query_group(db, name="qg-dev1", query_id=query.id, member=device, subscriber=artifact)
        await self._make_generator(
            db, name="device-generator", query_name="GetGenDevice", group=group, repo_node=repo_node
        )
        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        return {"device_id": device.id}

    def _unread_field_diff(self, *, target_branch: str, device_id: str) -> list[NodeDiff]:
        # "color" sits on the device kind the generator targets but is absent from the artifact query, so
        # the generator is selected on the kind while the artifact resolves to zero impacted members.
        return [
            node_diff(
                node_id=device_id,
                kind=DEVICE_KIND,
                branch=target_branch,
                action="UPDATED",
                display_label="device",
                field_names=["color"],
            )
        ]

    async def test_merge_regenerates_artifacts_after_generator(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A merge regenerates every artifact once its after-merge generator has run."""
        await self._run_follow_up(
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=self._unread_field_diff(target_branch=default_branch.name, device_id=dataset["device_id"]),
        )
        generator_models = self._generator_run_models(workflow_recorder)
        assert [model.generator_definition.definition_name for model in generator_models] == ["device-generator"]
        # The diff touches no field the artifact reads, so it is never selected on its own merit; the
        # after-merge generator run is the only reason to regenerate it, via the blanket artifact trigger.
        assert self._artifact_requests(workflow_recorder) == []
        trigger_branches = [
            call["parameters"]["branch"]
            for call in workflow_recorder.get_submit_calls_for(TRIGGER_ARTIFACT_DEFINITION_GENERATE)
        ]
        assert trigger_branches == [default_branch.name]

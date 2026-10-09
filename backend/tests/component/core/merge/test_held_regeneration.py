from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.protocols import CoreRepository

from infrahub import config, lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch.tasks import post_process_branch_merge
from infrahub.core.constants import (
    FullRegenerationReason,
    InfrahubKind,
    RepositoryDeliveryStatus,
    RepositoryInternalStatus,
)
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.manager import NodeManager
from infrahub.core.merge.builder import build_post_merge_regeneration_dispatcher, build_regeneration_barrier
from infrahub.core.node import Node
from infrahub.core.protocols import CoreGeneratorDefinition
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.generators.models import RequestGeneratorDefinitionRun
from infrahub.generators.tasks import run_generator_definition
from infrahub.git.models import GitRepositoryMerge, RequestArtifactDefinitionGenerate
from infrahub.git.tasks import generate_artifact_definition, merge_git_repository
from infrahub.git.writeback.models import HeldItem, HeldRegeneration, HeldWiden, PendingMerge
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.server import app
from infrahub.workers.dependencies import build_client
from infrahub.workflows.catalogue import (
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)
from tests.adapters.workflow import WorkflowRecorder
from tests.component.proposed_change.conftest import make_node_diff
from tests.helpers.dependency_override import override_dependency
from tests.helpers.git import LocalRemote
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppWithoutLocalWorkflow
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
    from pathlib import Path

    from fast_depends import Provider
    from prefect.client.schemas.objects import State

    from infrahub.core.branch import Branch
    from infrahub.core.merge.regeneration_dispatcher import PostMergeRegenerationDispatcher
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services import InfrahubServices
    from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo
    from tests.adapters.cache import MemoryCache
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

DEVICE_KIND = "TestNetworkDevice"
DIFF_CACHE_KEY = "held-regeneration-merge"
TRUNK = "main"
GENERATOR_RUN = REQUEST_GENERATOR_DEFINITION_RUN.name
ARTIFACT_GENERATE = REQUEST_ARTIFACT_DEFINITION_GENERATE.name

DEVICE_QUERY = """
query GetDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

HELD_REGENERATION_SCHEMA = SchemaRoot(
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
                AttributeSchema(
                    name="x_summary",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="x-python-transform"
                    ),
                ),
                AttributeSchema(
                    name="y_summary",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON, transform="y-python-transform"
                    ),
                ),
            ],
        )
    ]
)


@dataclass(frozen=True)
class OwnedDefinitions:
    """A repository with one artifact definition, one generator definition and one Python transform."""

    repository_id: str
    repository_name: str
    artifact_definition_id: str
    generator_definition_id: str
    jinja_transform_id: str


@dataclass(frozen=True)
class HeldRegenerationData:
    pending: OwnedDefinitions
    """The repository whose merges wait for their push to `remote`."""
    other: OwnedDefinitions
    """A repository with no pending delivery."""
    remote: LocalRemote
    group_id: str
    changed_device_id: str
    """The device that the merge renames."""
    unchanged_device_id: str


@dataclass(frozen=True)
class RepositoryView:
    """The commit that the regeneration flows read for a repository, and its held regeneration."""

    commit: str | None
    held: HeldRegeneration


class ObservingWorkflowRecorder(WorkflowRecorder):
    """Record each workflow call together with what `observe` reads at the moment of the call."""

    def __init__(self) -> None:
        super().__init__()
        self.observe: Callable[[], Awaitable[object]] | None = None

    def reset(self) -> None:
        super().reset()
        self.observe = None

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
        result = await super().execute_workflow(
            workflow=workflow,
            expected_return=expected_return,
            context=context,
            parameters=parameters,
            tags=tags,
            priority=priority,
        )
        await self._observe()
        return result

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        info = await super().submit_workflow(
            workflow=workflow, context=context, parameters=parameters, tags=tags, priority=priority
        )
        await self._observe()
        return info

    async def _observe(self) -> None:
        if self.observe is not None:
            self.calls[-1]["observed"] = await self.observe()


@dataclass(frozen=True)
class HeldRegenerationHarness:
    """Run the follow-up of a merge and the delivery of the pending repository with the real components."""

    dataset: HeldRegenerationData
    client: InfrahubClient
    store: WritebackIntentStore
    dispatcher: PostMergeRegenerationDispatcher
    recorder: ObservingWorkflowRecorder
    cache: MemoryCache
    context: InfrahubContext

    @property
    def pending(self) -> OwnedDefinitions:
        return self.dataset.pending

    @property
    def delivered_message(self) -> str:
        return f"The delivery to repository {self.pending.repository_name} ended with the outcome delivered."

    def trunk_head(self) -> str:
        return self.dataset.remote.repo.commit(TRUNK).hexsha

    async def view(self) -> RepositoryView:
        """Read the pending repository as the regeneration flows and the delivery read it."""
        repository = await self.client.get(kind=CoreRepository, id=self.pending.repository_id, branch=TRUNK)
        intent = await self.store.read(repository_id=self.pending.repository_id)
        return RepositoryView(commit=repository.commit.value, held=intent.held)

    def new_merge(self) -> PendingMerge:
        """Commit a change on a new remote branch, and return the queue entry of its merge."""
        git_branch = f"feature-{uuid4().hex[:8]}"
        commit = self.dataset.remote.commit(branch_name=git_branch, files={f"{git_branch}.txt": f"{git_branch}\n"})
        return PendingMerge(
            entry_id=str(uuid4()),
            source_branch=git_branch,
            source_git_branch=git_branch,
            source_commit=commit,
            merged_at=datetime.now(UTC),
        )

    async def enqueue(self, entry: PendingMerge) -> None:
        await self.store.enqueue(repository_id=self.pending.repository_id, entry=entry, widen=False)

    async def dispatch_merge(self) -> None:
        """Run the follow-up of a merge that renamed the changed device."""
        await DiffSummaryCache(cache=self.cache, serializer=DiffSummarySerializer(), key_namespace="branch_merge").set(
            diff_id=DIFF_CACHE_KEY,
            diff_summary=[make_node_diff(self.dataset.changed_device_id, DEVICE_KIND, TRUNK, ["name"])],
        )
        await self.dispatcher.dispatch(
            context=self.context, target_branch=TRUNK, merge_diff_cache_key=DIFF_CACHE_KEY, releasing=None
        )

    async def deliver(
        self, *, entry: PendingMerge, enqueued: bool, observe: Callable[[], Awaitable[object]] | None = None
    ) -> State:
        """Run the merge flow of the pending repository, and record only its own workflow calls."""
        self.recorder.reset()
        self.recorder.observe = observe or self.view
        model = GitRepositoryMerge(
            repository_id=self.pending.repository_id,
            repository_name=self.pending.repository_name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_branch=entry.source_branch,
            destination_branch=TRUNK,
            destination_branch_id=str(uuid4()),
            repository_kind=InfrahubKind.REPOSITORY,
            pending_merge=entry,
            pending_merge_enqueued=enqueued,
        )
        return await merge_git_repository(model=model, context=self.context, return_state=True)


async def _set_execute_after_merge(*, db: InfrahubDatabase, generator_definition_id: str, value: bool) -> None:
    generator = await NodeManager.get_one(
        db=db, id=generator_definition_id, kind=CoreGeneratorDefinition, raise_on_error=True
    )
    generator.execute_after_merge.value = value
    await generator.save(db=db)


def describe(call: dict[str, Any]) -> tuple[Any, ...]:
    """Name a call by its workflow, and a selective request also by its definition and its narrowing."""
    parameters = call["parameters"]
    model = parameters.get("model")
    if isinstance(model, RequestGeneratorDefinitionRun):
        return (call["kind"], call["workflow"].name, model.generator_definition.definition_id, model.target_members)
    if isinstance(model, RequestArtifactDefinitionGenerate):
        return (call["kind"], call["workflow"].name, model.artifact_definition_id, model.members)
    return (
        call["kind"],
        call["workflow"].name,
        {name: value for name, value in parameters.items() if name != "context"},
    )


def repository_regeneration(*, repository_id: str, python_attribute: str) -> list[tuple[Any, ...]]:
    """The calls that regenerate every definition of the repository and the Python attribute that it owns."""
    return [
        (
            "submit",
            TRIGGER_ARTIFACT_DEFINITION_GENERATE.name,
            {"branch": TRUNK, "include_repository_ids": [repository_id]},
        ),
        (
            "submit",
            TRIGGER_GENERATOR_DEFINITION_RUN.name,
            {"branch": TRUNK, "source": GeneratorDefinitionRunSource.MERGE, "include_repository_ids": [repository_id]},
        ),
        (
            "submit",
            TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES.name,
            {
                "branch_name": TRUNK,
                "computed_attribute_name": python_attribute,
                "computed_attribute_kind": DEVICE_KIND,
                "coalesced": True,
                "widened": True,
                "recompute_depth": 0,
            },
        ),
    ]


class TestHeldRegeneration(TestInfrahubAppWithoutLocalWorkflow):
    """A merge holds the regeneration of a repository whose merges wait for their push, and the delivery releases it.

    The delivery pushes to a remote on disk through the merge flow. At each dispatch, the recording workflow reads
    the commit of the repository, which the regeneration flows read when they run.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self, service: InfrahubServices, dependency_provider: Provider
    ) -> AsyncGenerator[ObservingWorkflowRecorder, None]:
        with override_workflow(ObservingWorkflowRecorder(), dependency_provider=dependency_provider) as recorder:
            yield recorder

    @pytest.fixture(scope="class", autouse=True)
    async def service(
        self, workflow_local: WorkflowLocalExecution, test_client: InfrahubTestClient
    ) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(scope="class")
    async def client(
        self,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        bus_simulator: BusSimulator,
        service: InfrahubServices,
        dependency_provider: Provider,
    ) -> AsyncGenerator[InfrahubClient, None]:
        sdk_client = InfrahubClient(
            config=Config(
                api_token=api_admin_token,
                requester=test_client.async_request,
                sync_requester=test_client.sync_request,
                schema_converge_timeout=5,
            )
        )
        original_client = service._client
        service._client = sdk_client
        try:
            with override_dependency(build_client, lambda: sdk_client, dependency_provider=dependency_provider):
                yield sdk_client
        finally:
            service._client = original_client

    @pytest.fixture(autouse=True)
    def enable_selective(self) -> Generator[None, None, None]:
        original = config.SETTINGS.main.selective_execution_after_merge
        config.SETTINGS.main.selective_execution_after_merge = True
        yield
        config.SETTINGS.main.selective_execution_after_merge = original

    @pytest.fixture(autouse=True)
    def machine_git_config_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep the Git configuration of the machine out of the replay, because it can sign or refuse a merge."""
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
        monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        tmp_path_module_scope: Path,
        git_repos_dir_module_scope: Path,
    ) -> HeldRegenerationData:
        await load_schema(db=db, schema=HELD_REGENERATION_SCHEMA, update_db=True)

        devices: list[Node] = []
        for name in ("dev1", "dev2"):
            device = await Node.init(db=db, schema=DEVICE_KIND)
            await device.new(db=db, name=name)
            await device.save(db=db)
            devices.append(device)

        # The analyzer fills `models` in production; a query saved directly must set it for the kind gate.
        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetDevice", query=DEVICE_QUERY, models=[DEVICE_KIND])
        await query.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="held-targets", members=devices)
        await group.save(db=db)

        # The remote has another branch checked out, so a push to its trunk is accepted.
        remote = LocalRemote.create(
            directory=tmp_path_module_scope / "pending-remote", trunk=TRUNK, branches=["parking"], head="parking"
        )
        pending, pending_subscribers = await self._create_owned_definitions(
            db=db,
            prefix="x",
            location=str(remote.directory),
            commit=remote.repo.commit(TRUNK).hexsha,
            query=query,
            group=group,
            devices=devices,
        )
        other, other_subscribers = await self._create_owned_definitions(
            db=db,
            prefix="y",
            location="https://github.com/test/held-regeneration-other.git",
            commit=None,
            query=query,
            group=group,
            devices=devices,
        )

        # The impact resolver finds the subscribers of a changed device through the query group of that device.
        for index, device in enumerate(devices):
            query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
            await query_group.new(
                db=db,
                name=f"held-query-group-{index}",
                query=query,
                members=[device],
                subscribers=[*pending_subscribers[index], *other_subscribers[index]],
            )
            await query_group.save(db=db)

        return HeldRegenerationData(
            pending=pending,
            other=other,
            remote=remote,
            group_id=group.id,
            changed_device_id=devices[0].id,
            unchanged_device_id=devices[1].id,
        )

    async def _create_owned_definitions(
        self,
        *,
        db: InfrahubDatabase,
        prefix: str,
        location: str,
        commit: str | None,
        query: Node,
        group: Node,
        devices: list[Node],
    ) -> tuple[OwnedDefinitions, list[list[Node]]]:
        """Create the repository and what it owns, and return the artifact and generator instance of each device."""
        repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repository.new(db=db, name=f"{prefix}-repository", location=location, default_branch=TRUNK, commit=commit)
        await repository.save(db=db)

        jinja_transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await jinja_transform.new(
            db=db,
            name=f"{prefix}-jinja-transform",
            query=query,
            repository=repository,
            template_path="templates/device.j2",
            dependencies=["templates/device.j2"],
            dependencies_complete=True,
        )
        await jinja_transform.save(db=db)

        # A definition with no fingerprint regenerates every member, so each one has a fingerprint.
        artifact_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await artifact_definition.new(
            db=db,
            name=f"{prefix}-artifact",
            targets=group,
            transformation=jinja_transform,
            content_type="text/plain",
            artifact_name=f"{prefix}-config",
            parameters={"value": {"name": "name__value"}},
            fingerprint=f"{prefix}-artifact-fingerprint",
        )
        await artifact_definition.save(db=db)

        generator_definition = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await generator_definition.new(
            db=db,
            name=f"{prefix}-generator",
            query=query,
            repository=repository,
            targets=group,
            file_path="generators/device.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
            convert_query_response=False,
            execute_in_proposed_change=False,
            execute_after_merge=True,
            dependencies=["generators/device.py"],
            dependencies_complete=True,
            fingerprint=f"{prefix}-generator-fingerprint",
        )
        await generator_definition.save(db=db)

        python_transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
        await python_transform.new(
            db=db,
            name=f"{prefix}-python-transform",
            query=query,
            repository=repository,
            file_path="transforms/device.py",
            class_name="DeviceTransform",
        )
        await python_transform.save(db=db)

        # A member with no artifact or generator instance always regenerates, so each device has both.
        subscribers: list[list[Node]] = []
        for device in devices:
            artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
            await artifact.new(
                db=db,
                name=f"{prefix}-config",
                definition=artifact_definition,
                status="Ready",
                object=device,
                content_type="text/plain",
            )
            await artifact.save(db=db)
            instance = await Node.init(db=db, schema=InfrahubKind.GENERATORINSTANCE)
            await instance.new(
                db=db,
                name=f"{prefix}-generator-instance",
                definition=generator_definition,
                object=device,
                status="Ready",
            )
            await instance.save(db=db)
            subscribers.append([artifact, instance])

        definitions = OwnedDefinitions(
            repository_id=repository.id,
            repository_name=f"{prefix}-repository",
            artifact_definition_id=artifact_definition.id,
            generator_definition_id=generator_definition.id,
            jinja_transform_id=jinja_transform.id,
        )
        return definitions, subscribers

    @pytest.fixture
    async def harness(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        dataset: HeldRegenerationData,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        client: InfrahubClient,
        workflow_recorder: ObservingWorkflowRecorder,
    ) -> HeldRegenerationHarness:
        workflow_recorder.reset()
        store = WritebackIntentStore(
            db=db, lock_registry=lock.registry, default_branch=default_branch, clock=partial(datetime.now, UTC)
        )
        dispatcher = await build_post_merge_regeneration_dispatcher(
            db=db,
            branch=default_branch,
            barrier=await build_regeneration_barrier(state=store, default_branch_name=default_branch.name),
            workflow=workflow_recorder,
            log=logging.getLogger(__name__),
        )
        context = InfrahubContext(
            branch=BranchContext(name=TRUNK),
            account=AccountSession(account_id=admin_account.id, auth_type=AuthType.API),
        )
        return HeldRegenerationHarness(
            dataset=dataset,
            client=client,
            store=store,
            dispatcher=dispatcher,
            recorder=workflow_recorder,
            cache=memory_cache,
            context=context,
        )

    async def test_a_pending_repository_waits_and_regenerates_once_after_its_delivery(
        self, harness: HeldRegenerationHarness
    ) -> None:
        pending, other = harness.pending, harness.dataset.other
        changed = harness.dataset.changed_device_id
        before = await harness.view()
        assert before.held.is_empty
        hold_seq = before.held.next_hold_seq

        entry = harness.new_merge()
        await harness.enqueue(entry)
        await harness.dispatch_merge()

        assert [describe(call) for call in harness.recorder.calls] == [
            ("execute", GENERATOR_RUN, other.generator_definition_id, [changed]),
            ("submit", ARTIFACT_GENERATE, other.artifact_definition_id, [changed]),
        ]
        held = (await harness.view()).held
        assert held.artifact_definitions == (HeldItem(id=pending.artifact_definition_id, hold_seq=hold_seq),)
        assert held.generator_definitions == (HeldItem(id=pending.generator_definition_id, hold_seq=hold_seq),)
        assert held.widen is None

        state = await harness.deliver(entry=entry, enqueued=True)

        assert state.message == harness.delivered_message
        delivered = harness.trunk_head()
        assert delivered != before.commit
        remote = harness.dataset.remote.repo
        assert remote.is_ancestor(remote.commit(entry.source_commit), remote.commit(delivered))
        assert [describe(call) for call in harness.recorder.calls] == [
            ("execute", GENERATOR_RUN, pending.generator_definition_id, [changed]),
            ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id, [changed]),
        ]
        assert [call["observed"].commit for call in harness.recorder.calls] == [delivered, delivered]
        after = await harness.store.read(repository_id=pending.repository_id)
        assert after.queue.entries == ()
        assert after.status == RepositoryDeliveryStatus.NONE
        assert after.held == HeldRegeneration(next_hold_seq=hold_seq + 1)

    async def test_a_deleted_held_definition_regenerates_every_definition_of_its_repository(
        self, db: InfrahubDatabase, harness: HeldRegenerationHarness
    ) -> None:
        pending, other = harness.pending, harness.dataset.other
        changed = harness.dataset.changed_device_id
        before = await harness.view()
        assert before.held.is_empty
        hold_seq = before.held.next_hold_seq
        deleted_definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await deleted_definition.new(
            db=db,
            name="x-deleted-artifact",
            targets=harness.dataset.group_id,
            transformation=pending.jinja_transform_id,
            content_type="text/plain",
            artifact_name="x-deleted-config",
            parameters={"value": {"name": "name__value"}},
            fingerprint="x-deleted-artifact-fingerprint",
        )
        await deleted_definition.save(db=db)

        entry = harness.new_merge()
        await harness.enqueue(entry)
        await harness.dispatch_merge()

        assert [describe(call) for call in harness.recorder.calls] == [
            ("execute", GENERATOR_RUN, other.generator_definition_id, [changed]),
            ("submit", ARTIFACT_GENERATE, other.artifact_definition_id, [changed]),
        ]
        held = (await harness.view()).held
        assert set(held.artifact_definitions) == {
            HeldItem(id=pending.artifact_definition_id, hold_seq=hold_seq),
            HeldItem(id=deleted_definition.id, hold_seq=hold_seq),
        }
        await deleted_definition.delete(db=db)

        state = await harness.deliver(entry=entry, enqueued=True)

        assert state.message == harness.delivered_message
        delivered = harness.trunk_head()
        assert delivered != before.commit
        assert [describe(call) for call in harness.recorder.calls] == repository_regeneration(
            repository_id=pending.repository_id, python_attribute="x_summary"
        )
        assert [call["observed"].commit for call in harness.recorder.calls] == [delivered] * 3
        after = await harness.store.read(repository_id=pending.repository_id)
        assert after.queue.entries == ()
        assert after.held == HeldRegeneration(next_hold_seq=hold_seq + 1)

    async def test_an_unqueued_merge_regenerates_its_repository_again_after_the_delivery(
        self, harness: HeldRegenerationHarness
    ) -> None:
        """The branch merge could not queue the merge, so its follow-up dispatched the work of the repository at once."""
        pending, other = harness.pending, harness.dataset.other
        changed = harness.dataset.changed_device_id
        before = await harness.view()
        assert before.held.is_empty
        hold_seq = before.held.next_hold_seq

        await harness.dispatch_merge()

        assert sorted(describe(call) for call in harness.recorder.calls) == sorted(
            [
                ("execute", GENERATOR_RUN, pending.generator_definition_id, [changed]),
                ("execute", GENERATOR_RUN, other.generator_definition_id, [changed]),
                ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id, [changed]),
                ("submit", ARTIFACT_GENERATE, other.artifact_definition_id, [changed]),
            ]
        )
        assert (await harness.view()).held == before.held

        state = await harness.deliver(entry=harness.new_merge(), enqueued=False)

        assert state.message == harness.delivered_message
        delivered = harness.trunk_head()
        assert delivered != before.commit
        assert [describe(call) for call in harness.recorder.calls] == repository_regeneration(
            repository_id=pending.repository_id, python_attribute="x_summary"
        )
        marker = HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=hold_seq)
        assert [(call["observed"].commit, call["observed"].held.widen) for call in harness.recorder.calls] == [
            (delivered, marker)
        ] * 3
        after = await harness.store.read(repository_id=pending.repository_id)
        assert after.queue.entries == ()
        assert after.held == HeldRegeneration(next_hold_seq=hold_seq + 1)

    async def test_a_full_release_runs_no_definition_of_another_pending_repository(
        self, harness: HeldRegenerationHarness
    ) -> None:
        pending, other = harness.pending, harness.dataset.other
        await harness.store.enqueue(repository_id=other.repository_id, entry=harness.new_merge(), widen=False)
        try:
            state = await harness.deliver(entry=harness.new_merge(), enqueued=False)

            assert state.message == harness.delivered_message
            assert [describe(call) for call in harness.recorder.calls] == repository_regeneration(
                repository_id=pending.repository_id, python_attribute="x_summary"
            )
            assert (await harness.store.read(repository_id=other.repository_id)).held.is_empty

            # The release submits the blanket triggers, so run them as the worker would.
            triggers = [
                call["parameters"]
                for call in harness.recorder.calls
                if call["workflow"].name
                in {TRIGGER_ARTIFACT_DEFINITION_GENERATE.name, TRIGGER_GENERATOR_DEFINITION_RUN.name}
            ]
            harness.recorder.reset()
            await generate_artifact_definition(context=harness.context, **triggers[0])
            await run_generator_definition(context=harness.context, **triggers[1])

            assert sorted(describe(call)[:3] for call in harness.recorder.calls) == sorted(
                [
                    ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id),
                    ("submit", GENERATOR_RUN, pending.generator_definition_id),
                ]
            )
        finally:
            other_intent = await harness.store.read(repository_id=other.repository_id)
            await harness.store.settle_delivery(
                repository_id=other.repository_id, snapshot=other_intent, delivered_commit=None
            )

    async def test_a_held_generator_that_no_longer_runs_after_a_merge_releases_nothing(
        self, db: InfrahubDatabase, harness: HeldRegenerationHarness
    ) -> None:
        pending = harness.pending
        changed = harness.dataset.changed_device_id
        before = await harness.view()
        assert before.held.is_empty
        hold_seq = before.held.next_hold_seq

        entry = harness.new_merge()
        await harness.enqueue(entry)
        await harness.dispatch_merge()
        held = (await harness.view()).held
        assert held.generator_definitions == (HeldItem(id=pending.generator_definition_id, hold_seq=hold_seq),)

        await _set_execute_after_merge(db=db, generator_definition_id=pending.generator_definition_id, value=False)
        try:
            state = await harness.deliver(entry=entry, enqueued=True)
        finally:
            await _set_execute_after_merge(db=db, generator_definition_id=pending.generator_definition_id, value=True)

        assert state.message == harness.delivered_message
        assert [describe(call) for call in harness.recorder.calls] == [
            ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id, [changed])
        ]
        after = await harness.store.read(repository_id=pending.repository_id)
        assert after.held == HeldRegeneration(next_hold_seq=hold_seq + 1)

    async def test_a_follow_up_with_selective_execution_off_holds_the_pending_repository(
        self, harness: HeldRegenerationHarness, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pending = harness.pending
        before = await harness.view()
        assert before.held.is_empty
        hold_seq = before.held.next_hold_seq
        monkeypatch.setattr(config.SETTINGS.main, "selective_execution_after_merge", False)
        monkeypatch.setattr(config.SETTINGS.main, "diff_update_after_merge", False)

        entry = harness.new_merge()
        await harness.enqueue(entry)
        try:
            await post_process_branch_merge(
                source_branch=entry.source_branch, target_branch=TRUNK, context=harness.context
            )

            assert [describe(call) for call in harness.recorder.calls] == [
                (
                    "submit",
                    TRIGGER_ARTIFACT_DEFINITION_GENERATE.name,
                    {"branch": TRUNK, "exclude_repository_ids": [pending.repository_id]},
                ),
                (
                    "submit",
                    TRIGGER_GENERATOR_DEFINITION_RUN.name,
                    {
                        "branch": TRUNK,
                        "source": GeneratorDefinitionRunSource.MERGE,
                        "exclude_repository_ids": [pending.repository_id],
                    },
                ),
            ]
            assert (await harness.view()).held == HeldRegeneration(
                next_hold_seq=hold_seq + 1,
                widen=HeldWiden(scope="all", reason=FullRegenerationReason.FEATURE_DISABLED, hold_seq=hold_seq),
            )
        finally:
            intent = await harness.store.read(repository_id=pending.repository_id)
            lease = await harness.store.settle_delivery(
                repository_id=pending.repository_id, snapshot=intent, delivered_commit=None
            )
            if lease is not None:
                await harness.store.clear_released(repository_id=pending.repository_id, lease_id=lease.lease_id)

    async def test_a_hold_during_a_release_survives_its_clear(self, harness: HeldRegenerationHarness) -> None:
        pending = harness.pending
        changed, unchanged = harness.dataset.changed_device_id, harness.dataset.unchanged_device_id
        before = await harness.view()
        assert before.held.is_empty
        hold_seq = before.held.next_hold_seq

        first = harness.new_merge()
        await harness.enqueue(first)
        await harness.dispatch_merge()

        second: list[PendingMerge] = []

        async def hold_again_then_view() -> RepositoryView:
            if not second:
                # A merge joins the queue while the release runs, and its follow-up holds the same definition again.
                second.append(harness.new_merge())
                await harness.enqueue(second[0])
                await harness.dispatcher.dispatch_requests(
                    context=harness.context,
                    target_branch=TRUNK,
                    generator_runs=[],
                    artifact_generates=[
                        RequestArtifactDefinitionGenerate(
                            branch=TRUNK,
                            artifact_definition_id=pending.artifact_definition_id,
                            artifact_definition_name="x-artifact",
                            members=[unchanged],
                            repository_id=pending.repository_id,
                        )
                    ],
                    releasing=None,
                    renew=None,
                )
            return await harness.view()

        state = await harness.deliver(entry=first, enqueued=True, observe=hold_again_then_view)

        assert state.message == harness.delivered_message
        first_delivered = harness.trunk_head()
        assert [describe(call) for call in harness.recorder.calls] == [
            ("execute", GENERATOR_RUN, pending.generator_definition_id, [changed]),
            ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id, [changed]),
        ]
        assert [call["observed"].commit for call in harness.recorder.calls] == [first_delivered] * 2
        between = await harness.store.read(repository_id=pending.repository_id)
        assert between.queue.entries == (second[0],)
        assert between.status == RepositoryDeliveryStatus.PENDING
        assert between.held == HeldRegeneration(
            next_hold_seq=hold_seq + 2,
            artifact_definitions=(HeldItem(id=pending.artifact_definition_id, hold_seq=hold_seq + 1),),
        )

        state = await harness.deliver(entry=second[0], enqueued=True)

        assert state.message == harness.delivered_message
        second_delivered = harness.trunk_head()
        assert second_delivered != first_delivered
        # The second hold joined its member to the narrowing that the first hold kept.
        assert [describe(call) for call in harness.recorder.calls] == [
            ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id, sorted([changed, unchanged]))
        ]
        assert [call["observed"].commit for call in harness.recorder.calls] == [second_delivered]
        after = await harness.store.read(repository_id=pending.repository_id)
        assert after.queue.entries == ()
        assert after.held == HeldRegeneration(next_hold_seq=hold_seq + 2)

    async def test_a_delivery_inside_the_hold_window_dispatches_what_an_unheld_merge_dispatches(
        self, harness: HeldRegenerationHarness
    ) -> None:
        pending, other = harness.pending, harness.dataset.other
        changed = harness.dataset.changed_device_id
        assert (await harness.view()).held.is_empty

        await harness.dispatch_merge()
        unheld = list(harness.recorder.calls)

        entry = harness.new_merge()
        await harness.enqueue(entry)
        harness.recorder.reset()
        await harness.dispatch_merge()
        held_merge = list(harness.recorder.calls)
        state = await harness.deliver(entry=entry, enqueued=True)
        released = list(harness.recorder.calls)

        assert state.message == harness.delivered_message
        expected = sorted(
            [
                ("execute", GENERATOR_RUN, pending.generator_definition_id, [changed]),
                ("execute", GENERATOR_RUN, other.generator_definition_id, [changed]),
                ("submit", ARTIFACT_GENERATE, pending.artifact_definition_id, [changed]),
                ("submit", ARTIFACT_GENERATE, other.artifact_definition_id, [changed]),
            ]
        )
        assert sorted(describe(call) for call in unheld) == expected
        assert sorted(describe(call) for call in [*held_merge, *released]) == expected
        assert sorted(call["parameters"]["model"].model_dump_json() for call in unheld) == sorted(
            call["parameters"]["model"].model_dump_json() for call in [*held_merge, *released]
        )

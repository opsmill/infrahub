from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestProposedChangeRunGenerators
from infrahub.proposed_change.tasks import run_generators
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_CHECK
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

from .conftest import make_node_diff

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.cache import MemoryCache
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient

SOURCE_BRANCH = "feature/generator-regen-selection"

QUERY_A = """
query GetADevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } } }
    }
}
"""

QUERY_B = """
query GetBDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } color { value } } }
    }
}
"""

QUERY_SOURCE_ONLY = """
query GetSourceOnlyDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } description { value } } }
    }
}
"""

# Each closure is set by hand rather than built by an import: these scenarios drive the
# selection gate, and the closure builder has its own tests. The shape matches what an import
# persists for a generator that declared its containing directory in `watch.files` - its own
# source file plus that directory's contents - together with the repository manifest, which is
# part of every closure. The closures are disjoint so a file edit selects exactly one generator.
DEPENDENCIES_A = [".infrahub.yml", "generators/a/__init__.py", "generators/a/a.py", "generators/a/helpers.py"]
DEPENDENCIES_A2 = [".infrahub.yml", "generators/a2/__init__.py", "generators/a2/a2.py"]
DEPENDENCIES_B = [".infrahub.yml", "generators/b/__init__.py", "generators/b/b.py"]
DEPENDENCIES_SOURCE_ONLY = [".infrahub.yml", "generators/new/__init__.py", "generators/new/new.py"]

GENERATOR_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            uniqueness_constraints=[["name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
        )
    ]
)


class GeneratorRegenTestBase(TestInfrahubAppBase):
    """Shared harness for the generator-regeneration selection-gate component tests.

    Provides the application wiring every scenario needs - a recording workflow backend so
    dispatched per-definition checks can be inspected without running them, an SDK client bound
    to the test server, and a per-test recorder reset - plus the machinery to drive
    ``run_generators`` and read back the set of generator definitions dispatched for a check.

    The ``workflow_recorder``, ``service`` and ``client`` fixtures override the base ones on
    purpose: the base ``client`` fixture assumes a ``WorkflowLocalExecution`` backend (it asserts
    on it) and would execute the dispatched checks, whereas these tests install a
    ``WorkflowRecorder`` so the dispatch itself is the observable under test. The base class also
    does not provide a ``service`` fixture at all (only the local-execution subclasses do).

    Subclasses supply their own schema and dataset inline. Each dataset must expose
    ``proposed_change_id``, ``repository_id``, ``repository_name`` and ``source_branch`` so the
    shared helpers can assemble the request.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: InfrahubTestClient) -> InfrahubServices:
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
        sdk_config = Config(
            api_token=api_admin_token,
            requester=test_client.async_request,
            sync_requester=test_client.sync_request,
            schema_converge_timeout=5,
        )
        sdk_client = InfrahubClient(config=sdk_config)
        original_client = service._client
        service._client = sdk_client
        with dependency_provider.scope(build_client, lambda: sdk_client):
            yield sdk_client
        service._client = original_client

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.reset()

    def _make_context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    async def _run_generators(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        diff_summary: list[dict],
        files_added: list[str] | None = None,
        files_changed: list[str] | None = None,
        files_removed: list[str] | None = None,
        read_only: bool = False,
        source_branch_sync_with_git: bool = True,
    ) -> None:
        pipeline_id = uuid.uuid4()
        repository = ProposedChangeRepository(
            repository_id=dataset["repository_id"],
            repository_name=dataset["repository_name"],
            read_only=read_only,
            source_branch=dataset["source_branch"],
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_commit="source-commit-sha",
            destination_commit="dest-commit-sha",
            files_added=files_added or [],
            files_changed=files_changed or [],
            files_removed=files_removed or [],
        )
        branch_diff = ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])
        await set_diff_summary_cache(pipeline_id=pipeline_id, diff_summary=diff_summary, cache=memory_cache)

        model = RequestProposedChangeRunGenerators(
            proposed_change=dataset["proposed_change_id"],
            source_branch=dataset["source_branch"],
            source_branch_sync_with_git=source_branch_sync_with_git,
            destination_branch=default_branch.name,
            branch_diff=branch_diff,
            refresh_artifacts=False,
            do_repository_checks=False,
        )
        await run_generators(model=model, context=self._make_context(admin_account, default_branch))

    async def _selected_definitions(
        self,
        *,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        diff_summary: list[dict],
        files_added: list[str] | None = None,
        files_changed: list[str] | None = None,
        files_removed: list[str] | None = None,
        read_only: bool = False,
        source_branch_sync_with_git: bool = True,
    ) -> list[str]:
        await self._run_generators(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=diff_summary,
            files_added=files_added,
            files_changed=files_changed,
            files_removed=files_removed,
            read_only=read_only,
            source_branch_sync_with_git=source_branch_sync_with_git,
        )
        return sorted(
            call["parameters"]["model"].generator_definition.definition_name
            for call in workflow_recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_CHECK)
        )


class TestGeneratorRegenSelection(GeneratorRegenTestBase):
    """The selection gate submits a per-definition check only for the generators a change affects.

    Drives the ``run_generators`` flow against four generator definitions backed by disjoint
    closures over a single repository, two of which share a query. Each scenario
    asserts the exact set of definitions dispatched, proving unrelated edits and sibling generators
    are left untouched while data changes, query edits and definition additions still select.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=GENERATOR_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="dev1", color="red", description="Device 1")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="generator-regen-repo", location="https://github.com/test/generator-regen-repo.git")
        await repo.save(db=db)

        # ``models`` is populated by the GraphQL mutation analyzer in production; nodes created
        # directly against the database must set it explicitly so the data-change (MODIFIED_KINDS)
        # path has the queried kinds to match against.
        query_a = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_a.new(db=db, name="GetADevice", query=QUERY_A, models=["TestNetworkDevice"])
        await query_a.save(db=db)

        query_b = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_b.new(db=db, name="GetBDevice", query=QUERY_B, models=["TestNetworkDevice"])
        await query_b.save(db=db)

        query_source_only = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_source_only.new(
            db=db, name="GetSourceOnlyDevice", query=QUERY_SOURCE_ONLY, models=["TestNetworkDevice"]
        )
        await query_source_only.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="generator-regen-targets", members=[device])
        await group.save(db=db)

        async def make_generator(
            *, name: str, query: Node, file_path: str, dependencies: list[str], branch: Branch | None = None
        ) -> Node:
            gendef = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION, branch=branch)
            await gendef.new(
                db=db,
                name=name,
                query=query,
                repository=repo,
                targets=group,
                file_path=file_path,
                class_name="DeviceGenerator",
                parameters={"value": {"name": "name__value"}},
                convert_query_response=False,
                execute_in_proposed_change=True,
                execute_after_merge=True,
                dependencies=dependencies,
                dependencies_complete=True,
            )
            await gendef.save(db=db)
            return gendef

        gendef_a = await make_generator(
            name="device-gen-a", query=query_a, file_path="generators/a/a.py", dependencies=DEPENDENCIES_A
        )
        gendef_a2 = await make_generator(
            name="device-gen-a2", query=query_a, file_path="generators/a2/a2.py", dependencies=DEPENDENCIES_A2
        )
        gendef_b = await make_generator(
            name="device-gen-b", query=query_b, file_path="generators/b/b.py", dependencies=DEPENDENCIES_B
        )

        source_branch_obj = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=GENERATOR_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        # A generator definition that exists only on the source branch reproduces the "new definition
        # on the source branch" edge case: it must be selected (and run for every target-group member)
        # even though the destination branch never saw it.
        gendef_source_only = await make_generator(
            name="device-gen-source-only",
            query=query_source_only,
            file_path="generators/new/new.py",
            dependencies=DEPENDENCIES_SOURCE_ONLY,
            branch=source_branch_obj,
        )

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db, name="generator-regen-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "repository_name": "generator-regen-repo",
            "source_branch": SOURCE_BRANCH,
            "device_id": device.id,
            "query_a_id": query_a.id,
            "query_b_id": query_b.id,
            "gendef_a_id": gendef_a.id,
            "gendef_a2_id": gendef_a2.id,
            "gendef_b_id": gendef_b.id,
            "gendef_source_only_id": gendef_source_only.id,
        }

    async def test_readme_edit_dispatches_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A repository edit outside every generator closure dispatches no generator."""
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

    async def test_unrelated_python_edit_dispatches_nothing(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A ``.py`` edit outside every package floor and unread by any query dispatches no generator."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=["scripts/unrelated.py"],
        )
        assert selected == []

    async def test_data_change_still_selects_via_modified_kinds(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A data change on a queried kind selects every generator reading that kind, unchanged by this feature.

        No repository file changed, so selection comes solely from the data-change path: every
        generator whose query reads the modified kind is dispatched exactly as before.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["device_id"], "TestNetworkDevice", SOURCE_BRANCH, ["name"])],
        )
        assert selected == ["device-gen-a", "device-gen-a2", "device-gen-b", "device-gen-source-only"]

    async def test_new_definition_on_source_branch_is_selected(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A definition present on the source branch but not the destination is selected when its node is added.

        The added definition node surfaces in the diff under its own id, so the definition-level
        signal selects it; no other generator matches the addition.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[
                make_node_diff(
                    dataset["gendef_source_only_id"],
                    InfrahubKind.GENERATORDEFINITION,
                    SOURCE_BRANCH,
                    ["file_path"],
                    action="ADDED",
                )
            ],
        )
        assert selected == ["device-gen-source-only"]

    async def test_source_edit_selects_only_owning_generator(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Editing a generator's own source file selects only the generator using it."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=["generators/a/a.py"],
        )
        assert selected == ["device-gen-a"]

    async def test_helper_in_stored_closure_selects_generator(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A closure member that is not the generator's own source file selects the owning generator.

        The gate treats every path in the stored closure alike, so a helper beside the source
        drives a re-run once it is in there. Whether it gets in there is the closure builder's
        decision, covered by its own tests.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=["generators/a/helpers.py"],
        )
        assert selected == ["device-gen-a"]

    async def test_query_edit_selects_only_owning_generator(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A query used by exactly one generator selects only that generator when modified."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_b_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
        )
        assert selected == ["device-gen-b"]

    async def test_query_edit_selects_every_consuming_generator(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A query shared by two generators selects both when modified."""
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_a_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
        )
        assert selected == ["device-gen-a", "device-gen-a2"]

    async def test_query_and_source_edit_dispatches_once(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """Editing both a generator's query and its source dispatches that generator exactly once.

        The shared query also selects the second consumer, but the generator whose source changed too
        is dispatched a single time - the two signals collapse into one per-definition selection.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[make_node_diff(dataset["query_a_id"], "CoreGraphQLQuery", SOURCE_BRANCH, ["query"])],
            files_changed=["generators/a/a.py"],
        )
        assert selected == ["device-gen-a", "device-gen-a2"]

    async def test_read_only_repo_closure_change_selects_without_git_sync(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A read-only repo bump that touches a closure selects even when the branch does not sync with Git.

        The selection gate keys on the per-repository file diff, not on ``source_branch_sync_with_git``,
        so a read-only repository whose tracked commit advances into a generator's closure re-runs that
        generator on a branch with ``sync_with_git = False`` - the read-only deployment pattern participates
        in precise triggering without any sync flag.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=["generators/a/a.py"],
            read_only=True,
            source_branch_sync_with_git=False,
        )
        assert selected == ["device-gen-a"]


class TestGeneratorRegenLegacyFallback(GeneratorRegenTestBase):
    """A generator imported before this feature (``dependencies=null``) runs under the legacy gate.

    Drives ``run_generators`` against a single generator whose stored closure is null, the state of
    every generator imported before this feature shipped. The selection gate must fall back to the
    pre-feature regenerate-on-any-file-change behavior with no error; self-heal on re-import (the
    closure being populated) is proven by the import-closure integration coverage, not here.
    """

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=GENERATOR_SCHEMA, update_db=True)

        device = await Node.init(db=db, schema="TestNetworkDevice")
        await device.new(db=db, name="legacy-dev", color="blue", description="Legacy device")
        await device.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(
            db=db, name="generator-legacy-repo", location="https://github.com/test/generator-legacy-repo.git"
        )
        await repo.save(db=db)

        query = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query.new(db=db, name="GetLegacyDevice", query=QUERY_A, models=["TestNetworkDevice"])
        await query.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="generator-legacy-targets", members=[device])
        await group.save(db=db)

        # A generator imported before this feature has no stored closure: both attributes are null.
        gendef = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef.new(
            db=db,
            name="device-gen-legacy",
            query=query,
            repository=repo,
            targets=group,
            file_path="generators/legacy/legacy.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
            convert_query_response=False,
            execute_in_proposed_change=True,
            execute_after_merge=True,
        )
        await gendef.save(db=db)

        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=GENERATOR_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db, name="generator-legacy-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "repository_name": "generator-legacy-repo",
            "source_branch": SOURCE_BRANCH,
            "gendef_legacy_id": gendef.id,
        }

    async def test_legacy_generator_runs_on_any_file_change(
        self,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        """A generator with ``dependencies=null`` is selected on any file change, with no error.

        An unrelated ``README.md`` edit would dispatch nothing for a generator carrying a complete
        closure; the null-closure generator instead falls back to the file-change signal and runs, so a
        pre-feature install never under-runs while it waits to self-heal on its next re-import.
        """
        selected = await self._selected_definitions(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            workflow_recorder=workflow_recorder,
            diff_summary=[],
            files_changed=["README.md"],
        )
        assert selected == ["device-gen-legacy"]

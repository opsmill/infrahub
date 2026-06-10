from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.proposed_change.branch_diff import set_diff_summary_cache
from infrahub.proposed_change.models import RequestGeneratorDefinitionCheck
from infrahub.proposed_change.tasks import request_generator_definition_check
from infrahub.server import app
from infrahub.workers.dependencies import build_client, build_workflow
from infrahub.workflows.catalogue import RUN_GENERATOR_AS_CHECK
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

from .conftest import QUERY_NON_UNIQUE_TARGETS, QUERY_UNIQUE_TARGETS, make_node_diff

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

SOURCE_BRANCH = "feature/generator-test"

# A unique-target query that reads the `tags` relationship in addition to `name`. Used to prove
# that a relationship endpoint flip on a field the query reads does trigger dispatch, while the
# same flip on a field the query ignores does not.
QUERY_UNIQUE_WITH_TAGS = """
query GetDeviceWithTags($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges {
            node {
                name { value }
                tags {
                    edges { node { name { value } } }
                }
            }
        }
    }
}
"""

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
                AttributeSchema(name="description", kind="Text", optional=True),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="tags",
                    peer=InfrahubKind.TAG,
                    optional=True,
                    cardinality="many",
                    kind="Attribute",
                ),
            ],
        )
    ]
)


@dataclass
class DiffEntry:
    id_key: str
    kind: str
    fields: list[str]
    element_type: str = "ATTRIBUTE"
    literal_id: bool = False


@dataclass
class GeneratorDispatchCase:
    name: str
    definition_key: str
    diff: list[DiffEntry]
    expected_keys: list[str]
    source_branch_sync_with_git: bool = False
    files_changed: list[str] | None = None


GENERATOR_DISPATCH_CASES = [
    GeneratorDispatchCase(
        name="unique_query_dispatches_only_instances_whose_read_field_changed",
        definition_key="gendef_unique",
        diff=[
            DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["name"]),
            DiffEntry(id_key="dev2_id", kind="TestNetworkDevice", fields=["description"]),
            DiffEntry(id_key="dev3_id", kind="TestNetworkDevice", fields=["name"]),
        ],
        expected_keys=["dev1_id", "dev3_id"],
    ),
    GeneratorDispatchCase(
        name="unique_query_dispatches_nothing_when_only_unread_field_changed",
        definition_key="gendef_unique",
        diff=[
            DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["description"]),
            DiffEntry(id_key="dev2_id", kind="TestNetworkDevice", fields=["description"]),
        ],
        expected_keys=[],
    ),
    GeneratorDispatchCase(
        name="unique_query_dispatches_nothing_when_changed_kind_not_queried",
        definition_key="gendef_unique",
        diff=[
            DiffEntry(
                id_key="00000000-0000-0000-0000-000000000000", kind=InfrahubKind.TAG, fields=["name"], literal_id=True
            )
        ],
        expected_keys=[],
    ),
    GeneratorDispatchCase(
        name="non_unique_query_dispatches_all_when_read_field_changed",
        definition_key="gendef_non_unique",
        diff=[DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["name"])],
        expected_keys=["dev1_id", "dev2_id", "dev3_id", "dev4_id"],
    ),
    GeneratorDispatchCase(
        name="non_unique_query_dispatches_nothing_when_no_read_field_changed",
        definition_key="gendef_non_unique",
        diff=[DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["description"])],
        expected_keys=[],
    ),
    GeneratorDispatchCase(
        name="managed_branch_dispatches_all_regardless_of_diff",
        definition_key="gendef_unique",
        diff=[DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["description"])],
        expected_keys=["dev1_id", "dev2_id", "dev3_id", "dev4_id"],
        source_branch_sync_with_git=True,
        files_changed=["generators/device.py"],
    ),
    GeneratorDispatchCase(
        name="new_target_without_instance_is_always_dispatched",
        definition_key="gendef_new",
        diff=[DiffEntry(id_key="dev_new_id", kind="TestNetworkDevice", fields=["name"])],
        expected_keys=["dev_new_id"],
    ),
    GeneratorDispatchCase(
        name="flip_on_unread_relationship_dispatches_nothing",
        definition_key="gendef_unique",
        diff=[DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["tags"], element_type="RELATIONSHIP_MANY")],
        expected_keys=[],
    ),
    GeneratorDispatchCase(
        name="flip_on_read_relationship_dispatches_matching_instance",
        definition_key="gendef_tags",
        diff=[DiffEntry(id_key="dev1_id", kind="TestNetworkDevice", fields=["tags"], element_type="RELATIONSHIP_MANY")],
        expected_keys=["dev1_id"],
    ),
]


class TestRequestGeneratorDefinitionCheck(TestInfrahubAppBase):
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
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

    @pytest.fixture(scope="class")
    async def generator_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        memory_cache: MemoryCache,
        admin_account: CoreAccount,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=GENERATOR_SCHEMA, update_db=True)

        # --- Devices on the default branch (inherited by the source branch on fork) ---
        dev1 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev1.new(db=db, name="dev1", color="red", description="Device 1")
        await dev1.save(db=db)

        dev2 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev2.new(db=db, name="dev2", color="blue", description="Device 2")
        await dev2.save(db=db)

        dev3 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev3.new(db=db, name="dev3", color="green", description="Device 3")
        await dev3.save(db=db)

        dev4 = await Node.init(db=db, schema="TestNetworkDevice")
        await dev4.new(db=db, name="dev4", color="yellow", description="Device 4")
        await dev4.save(db=db)

        # A device with no generator instance, used to exercise the "new target" branch.
        dev_new = await Node.init(db=db, schema="TestNetworkDevice")
        await dev_new.new(db=db, name="dev-new", color="black", description="New device")
        await dev_new.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(
            db=db,
            name="test-generator-repo",
            location="https://github.com/test/generator-repo.git",
        )
        await repo.save(db=db)

        query_unique = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_unique.new(db=db, name="GetNetworkDevice", query=QUERY_UNIQUE_TARGETS)
        await query_unique.save(db=db)

        query_non_unique = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_non_unique.new(db=db, name="GetAllNetworkDevices", query=QUERY_NON_UNIQUE_TARGETS)
        await query_non_unique.save(db=db)

        query_tags = await Node.init(db=db, schema="CoreGraphQLQuery")
        await query_tags.new(db=db, name="GetDeviceWithTags", query=QUERY_UNIQUE_WITH_TAGS)
        await query_tags.save(db=db)

        # --- Target group with the four devices that have instances ---
        targets_group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await targets_group.new(db=db, name="generator-targets", members=[dev1, dev2, dev3, dev4])
        await targets_group.save(db=db)

        gendef_node = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef_node.new(
            db=db,
            name="device-generator",
            query=query_unique,
            repository=repo,
            targets=targets_group,
            file_path="generators/device.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
            convert_query_response=False,
            execute_in_proposed_change=True,
            execute_after_merge=True,
        )
        await gendef_node.save(db=db)

        # --- Separate definition + group for the new-target scenario ---
        new_group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await new_group.new(db=db, name="generator-targets-new", members=[dev_new])
        await new_group.save(db=db)

        gendef_new_node = await Node.init(db=db, schema=InfrahubKind.GENERATORDEFINITION)
        await gendef_new_node.new(
            db=db,
            name="device-generator-new",
            query=query_unique,
            repository=repo,
            targets=new_group,
            file_path="generators/device.py",
            class_name="DeviceGenerator",
            parameters={"value": {"name": "name__value"}},
            convert_query_response=False,
            execute_in_proposed_change=True,
            execute_after_merge=True,
        )
        await gendef_new_node.save(db=db)

        # --- Source branch is created after all AWARE nodes exist on main ---
        source_branch_obj = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=GENERATOR_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        # --- Generator instances on the source branch (one per device in the main group) ---
        instances = {}
        for device in (dev1, dev2, dev3, dev4):
            instance = await Node.init(db=db, schema=InfrahubKind.GENERATORINSTANCE, branch=source_branch_obj)
            await instance.new(
                db=db,
                name=f"instance-{device.name.value}",
                status=GeneratorInstanceStatus.READY.value,
                object=device,
                definition=gendef_node,
            )
            await instance.save(db=db)
            instances[device.id] = instance

        # --- Query groups linking each device (member) to its instance (subscriber) ---
        for device in (dev1, dev2, dev3, dev4):
            query_group = await Node.init(db=db, schema="CoreGraphQLQueryGroup", branch=source_branch_obj)
            await query_group.new(
                db=db,
                name=f"qg-{device.name.value}",
                query=str(query_unique.id),
                members=[device],
                subscribers=[instances[device.id]],
            )
            await query_group.save(db=db)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db,
            name="test-generator-pc",
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
        )
        await pc.save(db=db)

        repository = ProposedChangeRepository(
            repository_id=repo.id,
            repository_name="test-generator-repo",
            read_only=False,
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            source_commit="source-commit-sha",
            destination_commit="dest-commit-sha",
        )

        def build_definition(query_name: str, query_payload: str, group_id: str) -> ProposedChangeGeneratorDefinition:
            return ProposedChangeGeneratorDefinition(
                definition_id=gendef_node.id if group_id == targets_group.id else gendef_new_node.id,
                definition_name="device-generator",
                query_name=query_name,
                query_models=["TestNetworkDevice"],
                query_payload=query_payload,
                repository_id=repo.id,
                class_name="DeviceGenerator",
                file_path="generators/device.py",
                group_id=group_id,
                parameters={"name": "name__value"},
                convert_query_response=False,
                execute_in_proposed_change=True,
                execute_after_merge=True,
            )

        return {
            "source_branch": SOURCE_BRANCH,
            "proposed_change_id": pc.id,
            "dev1_id": dev1.id,
            "dev2_id": dev2.id,
            "dev3_id": dev3.id,
            "dev4_id": dev4.id,
            "dev_new_id": dev_new.id,
            "repository": repository,
            "gendef_unique": build_definition("GetNetworkDevice", QUERY_UNIQUE_TARGETS, targets_group.id),
            "gendef_non_unique": build_definition("GetAllNetworkDevices", QUERY_NON_UNIQUE_TARGETS, targets_group.id),
            "gendef_tags": build_definition("GetDeviceWithTags", QUERY_UNIQUE_WITH_TAGS, targets_group.id),
            "gendef_new": build_definition("GetNetworkDevice", QUERY_UNIQUE_TARGETS, new_group.id),
        }

    def _make_context(self, account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext(
            branch=BranchContext(name=default_branch.name),
            account=AccountSession(account_id=account.id, auth_type=AuthType.API),
        )

    def _make_branch_diff(
        self,
        dataset: dict[str, Any],
        pipeline_id: uuid.UUID,
        files_changed: list[str] | None = None,
    ) -> ProposedChangeBranchDiff:
        repository = dataset["repository"]
        if files_changed:
            repository = ProposedChangeRepository(
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
                read_only=repository.read_only,
                source_branch=repository.source_branch,
                destination_branch=repository.destination_branch,
                internal_status=repository.internal_status,
                source_commit=repository.source_commit,
                destination_commit=repository.destination_commit,
                files_changed=files_changed,
            )
        return ProposedChangeBranchDiff(pipeline_id=pipeline_id, repositories=[repository])

    async def _run(
        self,
        definition: ProposedChangeGeneratorDefinition,
        dataset: dict[str, Any],
        context: InfrahubContext,
        diff_summary: list[dict],
        memory_cache: MemoryCache,
        default_branch: Branch,
        source_branch_sync_with_git: bool = False,
        files_changed: list[str] | None = None,
    ) -> None:
        pipeline_id = uuid.uuid4()
        branch_diff = self._make_branch_diff(dataset, pipeline_id, files_changed=files_changed)
        await set_diff_summary_cache(pipeline_id=pipeline_id, diff_summary=diff_summary, cache=memory_cache)
        model = RequestGeneratorDefinitionCheck(
            generator_definition=definition,
            branch_diff=branch_diff,
            proposed_change=dataset["proposed_change_id"],
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=source_branch_sync_with_git,
            destination_branch=default_branch.name,
        )
        await request_generator_definition_check(model=model, context=context)

    @staticmethod
    def _dispatched_target_ids(workflow_recorder: WorkflowRecorder) -> set[str]:
        return {
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(RUN_GENERATOR_AS_CHECK)
        }

    @pytest.mark.parametrize("case", GENERATOR_DISPATCH_CASES, ids=lambda case: case.name)
    async def test_generator_dispatch(
        self,
        case: GeneratorDispatchCase,
        generator_dataset: dict[str, Any],
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        context = self._make_context(admin_account, default_branch)
        diff_summary = [
            make_node_diff(
                entry.id_key if entry.literal_id else generator_dataset[entry.id_key],
                entry.kind,
                SOURCE_BRANCH,
                entry.fields,
                element_type=entry.element_type,
            )
            for entry in case.diff
        ]
        await self._run(
            generator_dataset[case.definition_key],
            generator_dataset,
            context,
            diff_summary,
            memory_cache,
            default_branch,
            source_branch_sync_with_git=case.source_branch_sync_with_git,
            files_changed=case.files_changed,
        )
        expected_targets = {generator_dataset[key] for key in case.expected_keys}
        assert self._dispatched_target_ids(workflow_recorder) == expected_targets

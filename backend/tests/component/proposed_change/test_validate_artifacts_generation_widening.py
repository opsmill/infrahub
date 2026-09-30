from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.proposed_change.tasks import validate_artifacts_generation
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, REQUEST_ARTIFACT_DEFINITION_CHECK
from tests.helpers.schema import load_schema

from .conftest import FLOW_RUN_LOGGER, ArtifactRegenTestBase, make_node_diff

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.proposed_change.models import RequestArtifactDefinitionCheck
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

SOURCE_BRANCH = "feature/artifact-widening"

# Pins one device per target and also reads the name of each tag, a kind reached through a relationship.
QUERY_UNIQUE_WITH_TAGS = """
query GetDeviceWithTags($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { name { value } tags { edges { node { name { value } } } } } }
    }
}
"""

# No filter pins a single device, so the query answers from every device.
QUERY_ALL_DEVICES = """
query GetAllDevices {
    TestNetworkDevice {
        edges { node { name { value } } }
    }
}
"""

# Pins one device per target and reads its human_friendly_id, which the device kind does not define.
QUERY_UNIQUE_WITH_HFID = """
query GetDeviceWithHfid($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges { node { hfid name { value } } }
    }
}
"""

DEPENDENCIES = [".infrahub.yml", "templates/device.j2"]

# No unique attribute, so the schema derives no human_friendly_id for the device kind.
ARTIFACT_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="NetworkDevice",
            namespace="Test",
            default_filter="name__value",
            display_label="name__value",
            inherit_from=["CoreArtifactTarget"],
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="tags", peer=InfrahubKind.TAG, optional=True, cardinality="many", kind="Attribute"
                ),
            ],
        )
    ]
)

DEVICES = ["dev1", "dev2", "dev3"]


@dataclass
class ArtifactWideningLogCase:
    name: str
    definition_name: str
    changed_device: str | None
    changed_kind: str
    expected_warnings: list[str]
    expected_devices: list[str]


ARTIFACT_WIDENING_LOG_CASES = [
    ArtifactWideningLogCase(
        name="non_unique_query_names_target_uniqueness",
        definition_name="artifact-all-devices",
        changed_device="dev1",
        changed_kind="TestNetworkDevice",
        expected_warnings=[
            "Artifact definition artifact-all-devices: the query does not guarantee unique targets. "
            "All targets will be processed."
        ],
        expected_devices=DEVICES,
    ),
    ArtifactWideningLogCase(
        name="change_on_a_related_kind_names_that_kind_not_target_uniqueness",
        definition_name="artifact-with-tags",
        changed_device=None,
        changed_kind=InfrahubKind.TAG,
        expected_warnings=[
            f"Artifact definition artifact-with-tags: the query reads {InfrahubKind.TAG} through a relationship, "
            "and a change there cannot be traced back to specific targets. All targets will be processed."
        ],
        expected_devices=DEVICES,
    ),
    ArtifactWideningLogCase(
        name="unscopable_derived_read_names_the_derived_read_not_target_uniqueness",
        definition_name="artifact-with-hfid",
        changed_device="dev1",
        changed_kind="TestNetworkDevice",
        expected_warnings=[
            "Artifact definition artifact-with-hfid: the query reads a human_friendly_id or display_label whose "
            "value cannot be traced back to specific targets. All targets will be processed."
        ],
        expected_devices=DEVICES,
    ),
    ArtifactWideningLogCase(
        name="narrowed_selection_logs_no_widening",
        definition_name="artifact-with-tags",
        changed_device="dev1",
        changed_kind="TestNetworkDevice",
        expected_warnings=[],
        expected_devices=["dev1"],
    ),
]


class TestValidateArtifactsGenerationWidening(ArtifactRegenTestBase):
    """The artifact validator explains in the task log why it processes every target."""

    @pytest.fixture(scope="class")
    async def dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        tag = await Node.init(db=db, schema=InfrahubKind.TAG)
        await tag.new(db=db, name="blue")
        await tag.save(db=db)

        devices: dict[str, Node] = {}
        for name in DEVICES:
            device = await Node.init(db=db, schema="TestNetworkDevice")
            await device.new(db=db, name=name, tags=[tag])
            await device.save(db=db)
            devices[name] = device

        repo = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repo.new(db=db, name="artifact-widening-repo", location="https://github.com/test/artifact-widening.git")
        await repo.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="artifact-widening-targets", members=list(devices.values()))
        await group.save(db=db)

        for definition_name, query_name, query_payload, query_models in (
            (
                "artifact-with-tags",
                "GetDeviceWithTags",
                QUERY_UNIQUE_WITH_TAGS,
                ["TestNetworkDevice", InfrahubKind.TAG],
            ),
            ("artifact-all-devices", "GetAllDevices", QUERY_ALL_DEVICES, ["TestNetworkDevice"]),
            ("artifact-with-hfid", "GetDeviceWithHfid", QUERY_UNIQUE_WITH_HFID, ["TestNetworkDevice"]),
        ):
            query = await Node.init(db=db, schema="CoreGraphQLQuery")
            await query.new(db=db, name=query_name, query=query_payload, models=query_models)
            await query.save(db=db)

            transform = await Node.init(db=db, schema="CoreTransformJinja2")
            await transform.new(
                db=db,
                name=f"render-{definition_name}",
                query=str(query.id),
                repository=str(repo.id),
                template_path="templates/device.j2",
                dependencies=DEPENDENCIES,
                dependencies_complete=True,
            )
            await transform.save(db=db)

            definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
            await definition.new(
                db=db,
                name=definition_name,
                targets=group,
                transformation=transform,
                content_type="text/plain",
                artifact_name=definition_name,
                parameters={"value": {"name": "name__value"}},
            )
            await definition.save(db=db)

            for device in devices.values():
                artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT)
                await artifact.new(
                    db=db,
                    name=definition_name,
                    status="Ready",
                    content_type="text/plain",
                    object=device,
                    definition=definition,
                )
                await artifact.save(db=db)

                # Rendering records which nodes the query returned; narrowing maps changed nodes back through it.
                query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
                await query_group.new(
                    db=db,
                    name=f"qg-{definition_name}-{device.id}",
                    query=str(query.id),
                    members=[device],
                    subscribers=[artifact],
                )
                await query_group.save(db=db)

        await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        pc = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await pc.new(
            db=db, name="artifact-widening-pc", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await pc.save(db=db)

        return {
            "proposed_change_id": pc.id,
            "repository_id": repo.id,
            "repository_name": "artifact-widening-repo",
            "source_branch": SOURCE_BRANCH,
            "tag_id": tag.id,
            "device_ids": {name: device.id for name, device in devices.items()},
        }

    @pytest.mark.parametrize("case", ARTIFACT_WIDENING_LOG_CASES, ids=lambda case: case.name)
    async def test_widening_warning_names_the_actual_reason(
        self,
        case: ArtifactWideningLogCase,
        dataset: dict[str, Any],
        default_branch: Branch,
        admin_account: CoreAccount,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        changed_id = dataset["device_ids"][case.changed_device] if case.changed_device else dataset["tag_id"]
        await self._refresh_artifacts(
            dataset=dataset,
            default_branch=default_branch,
            admin_account=admin_account,
            memory_cache=memory_cache,
            diff_summary=[make_node_diff(changed_id, case.changed_kind, SOURCE_BRANCH, ["name"])],
        )
        check_model = self._submitted_check(workflow_recorder, definition_name=case.definition_name)
        workflow_recorder.reset()

        with caplog.at_level(logging.INFO, logger=FLOW_RUN_LOGGER):
            await validate_artifacts_generation(
                model=check_model, context=self._make_context(admin_account, default_branch)
            )

        warnings = [
            record.getMessage()
            for record in caplog.records
            if record.levelno == logging.WARNING and record.getMessage().startswith("Artifact definition ")
        ]
        assert warnings == case.expected_warnings
        assert {
            call["parameters"]["model"].target_id
            for call in workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
        } == {dataset["device_ids"][name] for name in case.expected_devices}

    @staticmethod
    def _submitted_check(workflow_recorder: WorkflowRecorder, definition_name: str) -> RequestArtifactDefinitionCheck:
        models = [
            call["parameters"]["model"]
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
            if call["parameters"]["model"].artifact_definition.definition_name == definition_name
        ]
        assert len(models) == 1
        return models[0]

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import CheckType, InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.proposed_change.branch_diff import get_diff_change_times_cache
from infrahub.proposed_change.models import RequestProposedChangePipeline
from infrahub.proposed_change.tasks import (
    refresh_artifacts,
    run_proposed_change_pipeline,
    validate_artifacts_generation,
)
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    REQUEST_ARTIFACT_DEFINITION_CHECK,
    REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
)
from tests.helpers.schema import load_schema

from .conftest import ArtifactRegenTestBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

SOURCE_BRANCH = "feature/artifact-revalidation"
DEFINITION_NAME = "device-config"

QUERY_DEVICE = """
query GetDevice($ids: [ID!]!) {
    TestNetworkDevice(ids: $ids) {
        edges {
            node {
                name { value }
                color { value }
            }
        }
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
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="description", kind="Text", optional=True),
                AttributeSchema(name="color", kind="Text", optional=True),
            ],
        )
    ]
)


@dataclass(frozen=True, kw_only=True)
class Dataset:
    proposed_change_id: str
    group_id: str
    definition_id: str
    query_id: str
    repository_id: str
    dev1_id: str
    dev2_id: str
    dev3_id: str
    dev2_artifact_id: str


@dataclass(frozen=True, kw_only=True)
class PipelineRun:
    pipeline_id: uuid.UUID
    validated_definitions: list[str]
    """The definitions that got a validation, by name."""
    rendered_targets: set[str]
    """The targets that got an artifact check, by id."""


class TestArtifactRevalidationPipeline(ArtifactRegenTestBase):
    """A new run of the artifact checks of a proposed change covers only what changed since the last successful one.

    Each scenario runs the pipeline, the selection of definitions and the validations in turn on a real
    branch diff, with the artifact checks themselves recorded rather than executed. The scenarios share
    one branch, so each one starts with a run that brings the validation up to date.
    """

    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, default_branch: Branch, client: InfrahubClient) -> Dataset:
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, update_db=True)

        devices: list[Node] = []
        for name, color in (("dev1", "red"), ("dev2", "blue"), ("dev3", "green")):
            device = await Node.init(db=db, schema="TestNetworkDevice")
            await device.new(db=db, name=name, color=color, description=f"Device {name}")
            await device.save(db=db)
            devices.append(device)
        dev1, dev2, dev3 = devices

        repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repository.new(db=db, name="revalidation-repo", location="https://github.com/test/revalidation.git")
        await repository.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(db=db, name="GetDevice", query=QUERY_DEVICE)
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transform.new(
            db=db,
            name="device-render",
            query=str(query.id),
            repository=str(repository.id),
            template_path="device.j2",
            dependencies=["device.j2"],
            dependencies_complete=True,
        )
        await transform.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="device-targets", members=[dev1, dev2])
        await group.save(db=db)

        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name=DEFINITION_NAME,
            targets=group,
            transformation=transform,
            content_type="application/json",
            artifact_name="device-config",
            parameters={"value": {"name": "name__value"}},
        )
        await definition.save(db=db)

        source_branch = await create_branch(branch_name=SOURCE_BRANCH, db=db)
        await load_schema(db=db, schema=ARTIFACT_SCHEMA, branch_name=SOURCE_BRANCH, update_db=False)

        artifacts: list[Node] = []
        for device in (dev1, dev2):
            artifact = await Node.init(db=db, schema=InfrahubKind.ARTIFACT, branch=source_branch)
            await artifact.new(
                db=db,
                name="device-config",
                definition=definition,
                status="Ready",
                object=device,
                storage_id=str(uuid.uuid4()),
                checksum="aaaa",
                content_type="application/json",
            )
            await artifact.save(db=db)
            artifacts.append(artifact)

            query_group = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP, branch=source_branch)
            await query_group.new(
                db=db, name=f"query-group-{device.id}", query=str(query.id), members=[device], subscribers=[artifact]
            )
            await query_group.save(db=db)

        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db, name="revalidation", source_branch=SOURCE_BRANCH, destination_branch=default_branch.name
        )
        await proposed_change.save(db=db)

        return Dataset(
            proposed_change_id=proposed_change.id,
            group_id=group.id,
            definition_id=definition.id,
            query_id=query.id,
            repository_id=repository.id,
            dev1_id=dev1.id,
            dev2_id=dev2.id,
            dev3_id=dev3.id,
            dev2_artifact_id=artifacts[1].id,
        )

    @pytest.fixture
    def context(self, admin_account: CoreAccount, default_branch: Branch) -> InfrahubContext:
        return self._make_context(admin_account, default_branch)

    @pytest.fixture
    async def failed_run(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> PipelineRun:
        """A run whose only check fails, after a run that brought the validation up to date."""
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        await self._update_device(db=db, device_id=dataset.dev2_id, color="orange")
        workflow_recorder.execute_results[GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name] = ValidatorConclusion.FAILURE
        try:
            return await self._run_artifact_checks(
                dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
            )
        finally:
            workflow_recorder.execute_results.pop(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name, None)

    async def _run_artifact_checks(
        self, *, dataset: Dataset, default_branch: Branch, context: InfrahubContext, workflow_recorder: WorkflowRecorder
    ) -> PipelineRun:
        workflow_recorder.reset()
        pipeline = RequestProposedChangePipeline(
            proposed_change=dataset.proposed_change_id,
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=False,
            destination_branch=default_branch.name,
            check_type=CheckType.ARTIFACT,
        )
        await run_proposed_change_pipeline(model=pipeline, context=context)

        refresh_calls = workflow_recorder.get_submit_calls_for(REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS)
        assert len(refresh_calls) == 1
        await refresh_artifacts(model=refresh_calls[0]["parameters"]["model"], context=context)

        validations = [
            call["parameters"]["model"]
            for call in workflow_recorder.get_submit_calls_for(REQUEST_ARTIFACT_DEFINITION_CHECK)
        ]
        for validation in validations:
            await validate_artifacts_generation(model=validation, context=context)

        return PipelineRun(
            pipeline_id=pipeline.pipeline_id,
            validated_definitions=[validation.artifact_definition.definition_name for validation in validations],
            rendered_targets={
                call["parameters"]["model"].target_id
                for call in workflow_recorder.get_execute_calls_for(GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE)
            },
        )

    async def _update_device(self, *, db: InfrahubDatabase, device_id: str, **values: str) -> None:
        device = await NodeManager.get_one(db=db, id=device_id, branch=SOURCE_BRANCH, raise_on_error=True)
        for name, value in values.items():
            device.get_attribute(name=name).value = value
        await device.save(db=db)

    async def _validator_status(self, *, db: InfrahubDatabase) -> tuple[str, str]:
        validators = await NodeManager.query(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        assert len(validators) == 1
        return validators[0].state.value.value, validators[0].conclusion.value.value

    async def test_run_without_a_new_change_validates_no_definition(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._update_device(db=db, device_id=dataset.dev1_id, name="dev1-renamed")

        first = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        second = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert first.validated_definitions == [DEFINITION_NAME]
        assert first.rendered_targets == {dataset.dev1_id}
        assert second.validated_definitions == []
        assert second.rendered_targets == set()
        assert await self._validator_status(db=db) == (
            ValidatorState.COMPLETED.value,
            ValidatorConclusion.SUCCESS.value,
        )
        first_times = await get_diff_change_times_cache(pipeline_id=first.pipeline_id, cache=memory_cache)
        second_times = await get_diff_change_times_cache(pipeline_id=second.pipeline_id, cache=memory_cache)
        assert first_times is not None
        assert second_times is not None
        assert second_times.from_time == first_times.from_time
        assert second_times.to_time > first_times.to_time

    async def test_run_after_a_change_renders_only_the_target_it_reaches(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        await self._update_device(db=db, device_id=dataset.dev2_id, color="purple")

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev2_id}

    async def test_run_after_a_value_is_changed_back_renders_its_target_again(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        await self._update_device(db=db, device_id=dataset.dev2_id, color="blue")

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev2_id}

    async def test_run_after_a_change_the_query_does_not_read_renders_nothing(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        await self._update_device(db=db, device_id=dataset.dev2_id, description="Edge device")

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == set()
        assert await self._validator_status(db=db) == (
            ValidatorState.COMPLETED.value,
            ValidatorConclusion.SUCCESS.value,
        )

    async def test_run_after_a_failed_check_covers_the_whole_diff_again(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        failed_run: PipelineRun,
    ) -> None:
        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert failed_run.rendered_targets == {dataset.dev2_id}
        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev1_id, dataset.dev2_id}

    async def _set_group_members(self, *, db: InfrahubDatabase, dataset: Dataset, member_ids: list[str]) -> None:
        group = await NodeManager.get_one(db=db, id=dataset.group_id, branch=SOURCE_BRANCH, raise_on_error=True)
        await group.members.update(db=db, data=member_ids)
        await group.save(db=db)

    async def test_run_after_a_member_with_an_artifact_joins_again_covers_the_whole_diff(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._set_group_members(db=db, dataset=dataset, member_ids=[dataset.dev1_id])
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        await self._set_group_members(db=db, dataset=dataset, member_ids=[dataset.dev1_id, dataset.dev2_id])

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev1_id, dataset.dev2_id}

    async def test_run_after_the_query_changes_renders_every_target(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        query = await NodeManager.get_one(db=db, id=dataset.query_id, branch=SOURCE_BRANCH, raise_on_error=True)
        query.get_attribute(name="query").value = f"{QUERY_DEVICE}# second revision\n"
        await query.save(db=db)

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev1_id, dataset.dev2_id}

    async def test_run_after_the_definition_changes_renders_every_target(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        definition = await NodeManager.get_one(
            db=db, id=dataset.definition_id, branch=SOURCE_BRANCH, raise_on_error=True
        )
        definition.get_attribute(name="description").value = "Rendered device configuration"
        await definition.save(db=db)

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev1_id, dataset.dev2_id}

    async def test_run_after_the_repository_commit_moves_covers_the_whole_diff(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        repository = await NodeManager.get_one(
            db=db, id=dataset.repository_id, branch=SOURCE_BRANCH, raise_on_error=True
        )
        repository.get_attribute(name="commit").value = "0123456789abcdef0123456789abcdef01234567"
        await repository.save(db=db)

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev1_id, dataset.dev2_id}

    async def test_run_after_a_member_joins_the_target_group_renders_it(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        await self._set_group_members(
            db=db, dataset=dataset, member_ids=[dataset.dev1_id, dataset.dev2_id, dataset.dev3_id]
        )

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]
        assert run.rendered_targets == {dataset.dev3_id}

    @pytest.mark.xfail(
        strict=True,
        reason="An artifact is local to its branch and absent from the branch diff, so its deletion selects nothing",
    )
    async def test_run_after_an_artifact_is_deleted_renders_its_target(
        self,
        db: InfrahubDatabase,
        dataset: Dataset,
        default_branch: Branch,
        context: InfrahubContext,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
    ) -> None:
        await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )
        artifact = await NodeManager.get_one(
            db=db, id=dataset.dev2_artifact_id, branch=SOURCE_BRANCH, raise_on_error=True
        )
        await artifact.delete(db=db)

        run = await self._run_artifact_checks(
            dataset=dataset, default_branch=default_branch, context=context, workflow_recorder=workflow_recorder
        )

        assert run.validated_definitions == [DEFINITION_NAME]

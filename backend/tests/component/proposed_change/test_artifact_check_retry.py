from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from infrahub_sdk.protocols import CoreArtifact, CoreArtifactCheck, CoreArtifactDefinition, CoreArtifactValidator

from infrahub.artifacts.models import ArtifactCheckResult, CheckArtifactCreate
from infrahub.artifacts.tasks import create
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.git.integrator import ArtifactGenerateResult
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeRepository,
)
from infrahub.proposed_change.models import RequestArtifactDefinitionCheck
from infrahub.proposed_change.tasks import _run_artifact_target
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE
from tests.adapters.workflow import WorkflowRecorder
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, save_schema
from tests.helpers.workflow_override import override_workflow

from .conftest import ArtifactRegenTestBase

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.context import InfrahubContext
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

SOURCE_BRANCH = "artifact-check-retry"


@dataclass(frozen=True, kw_only=True)
class Dataset:
    repository_id: str
    definition_id: str
    query_id: str
    target_id: str


class SuccessfulArtifactRepository:
    async def render_artifact(
        self, *, artifact: CoreArtifact, artifact_created: bool, message: CheckArtifactCreate
    ) -> ArtifactGenerateResult:
        artifact.status.value = "Ready"
        await artifact.save()
        return ArtifactGenerateResult(
            changed=True, checksum="rendered-checksum", storage_id="rendered-storage", artifact_id=artifact.id
        )


async def unavailable_repository(**kwargs: object) -> SuccessfulArtifactRepository:
    raise RuntimeError("Repository setup failed")


async def successful_repository(**kwargs: object) -> SuccessfulArtifactRepository:
    return SuccessfulArtifactRepository()


async def cancelled_repository(**kwargs: object) -> SuccessfulArtifactRepository:
    raise asyncio.CancelledError


class TerminalArtifactWorkflow(WorkflowRecorder):
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
        if workflow != GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE:
            return result
        assert parameters is not None
        model = parameters["model"]
        assert isinstance(model, CheckArtifactCreate)
        try:
            return await create(model=model)
        except asyncio.CancelledError as exc:
            raise RuntimeError("Artifact worker terminated without a result") from exc


class TestArtifactCheckRetry(ArtifactRegenTestBase):
    @pytest.fixture(scope="class")
    async def dataset(self, db: InfrahubDatabase, client: InfrahubClient) -> Dataset:
        await save_schema(db=db, schema=CAR_SCHEMA)
        target = await Node.init(db=db, schema=TestKind.PERSON)
        await target.new(db=db, name="before-rename")
        await target.save(db=db)

        repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await repository.new(db=db, name="artifact-check-retry", location="https://github.com/test/artifacts.git")
        await repository.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
        await group.new(db=db, name="artifact-check-targets", members=[target])
        await group.save(db=db)

        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(
            db=db,
            name="ArtifactCheckTarget",
            query="query ArtifactCheckTarget { TestingPerson { edges { node { name { value } } } } }",
            models=[TestKind.PERSON],
        )
        await query.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
        await transform.new(
            db=db,
            name="artifact-check-transform",
            query=query,
            repository=repository,
            template_path="template.j2",
        )
        await transform.save(db=db)

        definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
        await definition.new(
            db=db,
            name="artifact-check-definition",
            artifact_name="startup-config",
            content_type="text/plain",
            targets=group,
            transformation=transform,
            parameters={"value": {}},
        )
        await definition.save(db=db)
        await create_branch(branch_name=SOURCE_BRANCH, db=db)

        return Dataset(
            repository_id=repository.get_id(),
            definition_id=definition.get_id(),
            query_id=query.get_id(),
            target_id=target.get_id(),
        )

    @pytest.fixture
    async def check_model(
        self,
        dataset: Dataset,
        db: InfrahubDatabase,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> CheckArtifactCreate:
        proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
        await proposed_change.new(
            db=db,
            name=f"artifact-check-{uuid4()}",
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
        )
        await proposed_change.save(db=db)
        validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
        await validator.new(db=db, proposed_change=proposed_change, definition=dataset.definition_id)
        await validator.save(db=db)
        return CheckArtifactCreate(
            artifact_name="startup-config",
            artifact_definition=dataset.definition_id,
            artifact_definition_name="artifact-check-definition",
            commit="commit",
            content_type="text/plain",
            transform_type=InfrahubKind.TRANSFORMJINJA2,
            transform_location="template.j2",
            repository_id=dataset.repository_id,
            repository_name="artifact-check-retry",
            repository_kind=InfrahubKind.REPOSITORY,
            branch_name=SOURCE_BRANCH,
            target_id=dataset.target_id,
            target_kind=TestKind.PERSON,
            target_name="before-rename",
            query="ArtifactCheckTarget",
            query_id=dataset.query_id,
            timeout=10,
            variables={},
            validator_id=validator.get_id(),
            context=self._make_context(admin_account, default_branch),
        )

    async def test_setup_failure_is_persisted_and_retry_updates_the_same_check_after_rename(
        self, check_model: CheckArtifactCreate, client: InfrahubClient
    ) -> None:
        with patch("infrahub.artifacts.tasks.get_initialized_repo", new=unavailable_repository):
            failed = await create(model=check_model)

        assert failed.conclusion == ValidatorConclusion.FAILURE
        assert failed.check_id is not None
        check = await client.get(kind=CoreArtifactCheck, id=failed.check_id)
        assert check.conclusion.value == ValidatorConclusion.FAILURE.value
        assert check.message.value == "Failed to render artifact: Repository setup failed"
        assert check.artifact_id.value is None
        assert await client.filters(kind=CoreArtifact, branch=SOURCE_BRANCH, object__ids=[check_model.target_id]) == []

        target = await client.get(kind=TestKind.PERSON, id=check_model.target_id, branch=SOURCE_BRANCH)
        target.name.value = "after-rename"
        await target.save()
        retry = check_model.model_copy(update={"check_id": failed.check_id, "target_name": "after-rename"})
        with patch("infrahub.artifacts.tasks.get_initialized_repo", new=successful_repository):
            succeeded = await create(model=retry)

        assert succeeded.conclusion == ValidatorConclusion.SUCCESS
        assert succeeded.check_id == failed.check_id
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[check_model.validator_id])
        assert len(checks) == 1
        check = checks[0]
        assert check.id == failed.check_id
        assert check.name.value == "startup-config: after-rename"
        assert check.message.value == "Artifact rendered successfully"
        assert check.conclusion.value == ValidatorConclusion.SUCCESS.value
        assert check.severity.value == "info"
        assert check.changed.value is True
        assert check.checksum.value == "rendered-checksum"
        assert check.storage_id.value == "rendered-storage"
        artifacts = await client.filters(kind=CoreArtifact, branch=SOURCE_BRANCH, object__ids=[check_model.target_id])
        assert len(artifacts) == 1
        assert check.artifact_id.value == artifacts[0].id

    async def test_cancelled_check_reuses_its_reserved_identity_on_retry(
        self, check_model: CheckArtifactCreate, client: InfrahubClient
    ) -> None:
        reserved_id = str(uuid4())
        check_model = check_model.model_copy(update={"check_id": reserved_id})
        with (
            patch("infrahub.artifacts.tasks.get_initialized_repo", new=cancelled_repository),
            pytest.raises(asyncio.CancelledError, match=r"^$"),
        ):
            await create(model=check_model)

        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[check_model.validator_id])
        assert len(checks) == 1
        assert checks[0].id == reserved_id
        assert checks[0].conclusion.value == ValidatorConclusion.UNKNOWN.value
        assert checks[0].message.value == "Rendering artifact"

        with patch("infrahub.artifacts.tasks.get_initialized_repo", new=successful_repository):
            succeeded = await create(model=check_model)

        assert succeeded.check_id == reserved_id
        assert succeeded.conclusion == ValidatorConclusion.SUCCESS
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[check_model.validator_id])
        assert len(checks) == 1
        assert checks[0].id == reserved_id
        assert checks[0].conclusion.value == ValidatorConclusion.SUCCESS.value
        assert checks[0].message.value == "Artifact rendered successfully"

    async def test_parent_keeps_reserved_check_identity_when_a_child_terminates_without_result(
        self,
        check_model: CheckArtifactCreate,
        client: InfrahubClient,
        default_branch: Branch,
        dependency_provider: Provider,
    ) -> None:
        validator = await client.get(kind=CoreArtifactValidator, id=check_model.validator_id)
        definition = await client.get(
            kind=CoreArtifactDefinition, id=check_model.artifact_definition, branch=SOURCE_BRANCH
        )
        target = await client.get(kind=TestKind.PERSON, id=check_model.target_id, branch=SOURCE_BRANCH)
        repository = ProposedChangeRepository(
            repository_id=check_model.repository_id,
            repository_name=check_model.repository_name,
            read_only=False,
            source_branch=SOURCE_BRANCH,
            destination_branch=default_branch.name,
            internal_status="active",
            source_commit=check_model.commit,
            destination_commit=check_model.commit,
        )
        request = RequestArtifactDefinitionCheck(
            artifact_definition=ProposedChangeArtifactDefinition(
                definition_id=definition.id,
                definition_name=check_model.artifact_definition_name,
                artifact_name=check_model.artifact_name,
                query_name=check_model.query,
                query_id=check_model.query_id,
                query_payload="query ArtifactCheckTarget { TestingPerson { edges { node { name { value } } } } }",
                repository_id=check_model.repository_id,
                transform_kind=check_model.transform_type,
                template_path=check_model.transform_location,
                content_type=check_model.content_type,
                timeout=check_model.timeout,
            ),
            branch_diff=ProposedChangeBranchDiff(pipeline_id=uuid4(), repositories=[repository]),
            proposed_change=validator.proposed_change.id,
            source_branch=SOURCE_BRANCH,
            source_branch_sync_with_git=True,
            destination_branch=default_branch.name,
        )

        async def run_target(previous_outcome: ArtifactCheckResult | None) -> ArtifactCheckResult:
            return await _run_artifact_target(
                model=request,
                context=check_model.context,
                artifact_definition=definition,
                member=target,
                artifact_id=None,
                validator_id=validator.id,
                previous_outcome=previous_outcome,
            )

        with (
            override_workflow(workflow=TerminalArtifactWorkflow(), dependency_provider=dependency_provider),
            patch("infrahub.proposed_change.tasks.get_run_logger", return_value=logging.getLogger(__name__)),
        ):
            with patch("infrahub.artifacts.tasks.get_initialized_repo", new=cancelled_repository):
                failed = await run_target(previous_outcome=None)
            assert failed.conclusion == ValidatorConclusion.FAILURE
            assert failed.check_id is not None
            checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[validator.id])
            assert len(checks) == 1
            assert checks[0].id == failed.check_id
            assert checks[0].conclusion.value == ValidatorConclusion.UNKNOWN.value

            with patch("infrahub.artifacts.tasks.get_initialized_repo", new=successful_repository):
                succeeded = await run_target(previous_outcome=failed)

        assert succeeded.conclusion == ValidatorConclusion.SUCCESS
        assert succeeded.check_id == failed.check_id
        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[validator.id])
        assert len(checks) == 1
        assert checks[0].id == failed.check_id
        assert checks[0].conclusion.value == ValidatorConclusion.SUCCESS.value
        assert checks[0].message.value == "Artifact rendered successfully"

    async def test_different_targets_with_the_same_label_keep_distinct_checks(
        self, check_model: CheckArtifactCreate, client: InfrahubClient
    ) -> None:
        other_target = await client.create(
            kind=TestKind.PERSON, branch=SOURCE_BRANCH, data={"name": check_model.target_name}
        )
        await other_target.save()
        other_model = check_model.model_copy(update={"target_id": other_target.id})
        with patch("infrahub.artifacts.tasks.get_initialized_repo", new=unavailable_repository):
            first = await create(model=check_model)
            second = await create(model=other_model)

        checks = await client.filters(kind=CoreArtifactCheck, validator__ids=[check_model.validator_id])
        assert len(checks) == 2
        assert first.check_id != second.check_id
        assert {check.id for check in checks} == {first.check_id, second.check_id}
        assert [check.name.value for check in checks] == ["startup-config: before-rename"] * 2
        assert [check.conclusion.value for check in checks] == [ValidatorConclusion.FAILURE.value] * 2

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub.core.constants import CheckType
from infrahub.message_bus.types import ProposedChangeBranchDiff
from infrahub.proposed_change.models import (
    RequestProposedChangePipeline,
    RequestProposedChangeRunGenerators,
)
from infrahub.proposed_change.tasks import run_generators, run_proposed_change_pipeline
from infrahub.workflows.catalogue import (
    REQUEST_GENERATOR_DEFINITION_CHECK,
    REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
    REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
    REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
)
from tests.adapters.workflow import WorkflowRecorder


def _make_generator_definition(name: str = "gen1", query_models: list[str] | None = None) -> MagicMock:
    """Create a mock CoreGeneratorDefinition with the attributes run_generators reads."""
    gen = MagicMock()
    gen.id = f"gen-{name}"
    gen.name.value = name
    gen.class_name.value = "MyGenerator"
    gen.file_path.value = "generators/my_gen.py"
    gen.query.peer.name.value = f"query-{name}"
    gen.query.peer.models.value = query_models or ["InfraDevice"]
    gen.repository.peer.id = "repo-1"
    gen.parameters.value = {}
    gen.targets.peer.id = "group-1"
    gen.convert_query_response.value = False
    gen.execute_in_proposed_change.value = True
    gen.execute_after_merge.value = True
    return gen


def _make_branch_diff(pipeline_id: uuid.UUID | None = None) -> ProposedChangeBranchDiff:
    return ProposedChangeBranchDiff(
        pipeline_id=pipeline_id or uuid.uuid4(),
        repositories=[],
        subscribers=[],
    )


@pytest.fixture
def workflow_recorder() -> WorkflowRecorder:
    return WorkflowRecorder()


class TestRunGenerators:
    """Tests for the refactored run_generators() function."""

    @pytest.mark.anyio
    async def test_generators_use_execute_workflow(self, workflow_recorder: WorkflowRecorder) -> None:
        """T013: Verify generator definition checks use execute_workflow (blocking), not submit_workflow."""
        pipeline_id = uuid.uuid4()
        model = RequestProposedChangeRunGenerators(
            proposed_change="pc-1",
            source_branch="branch1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            branch_diff=_make_branch_diff(pipeline_id),
        )

        mock_client = AsyncMock()
        mock_client.filters = AsyncMock(return_value=[_make_generator_definition()])

        with (
            patch("infrahub.proposed_change.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.proposed_change.tasks.get_client", return_value=mock_client),
            patch("infrahub.proposed_change.tasks.get_workflow", return_value=workflow_recorder),
            patch(
                "infrahub.proposed_change.tasks.get_diff_summary_cache",
                new_callable=AsyncMock,
                return_value=[{"branch": "branch1", "kind": "InfraDevice", "actions": ["update"], "id": "obj-1"}],
            ),
        ):
            await run_generators.fn(model=model, context=MagicMock())

        # Generator definition checks should use execute_workflow
        gen_execute_calls = workflow_recorder.get_execute_calls_for(REQUEST_GENERATOR_DEFINITION_CHECK)
        assert len(gen_execute_calls) == 1

        # Should NOT appear in submit_calls
        gen_submit_calls = workflow_recorder.get_submit_calls_for(REQUEST_GENERATOR_DEFINITION_CHECK)
        assert len(gen_submit_calls) == 0

    @pytest.mark.anyio
    async def test_no_artifact_dispatch_from_run_generators(self, workflow_recorder: WorkflowRecorder) -> None:
        """T014: Verify run_generators does not dispatch artifact refresh."""
        pipeline_id = uuid.uuid4()
        model = RequestProposedChangeRunGenerators(
            proposed_change="pc-1",
            source_branch="branch1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            branch_diff=_make_branch_diff(pipeline_id),
        )

        mock_client = AsyncMock()
        mock_client.filters = AsyncMock(return_value=[_make_generator_definition()])

        with (
            patch("infrahub.proposed_change.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.proposed_change.tasks.get_client", return_value=mock_client),
            patch("infrahub.proposed_change.tasks.get_workflow", return_value=workflow_recorder),
            patch(
                "infrahub.proposed_change.tasks.get_diff_summary_cache",
                new_callable=AsyncMock,
                return_value=[{"branch": "branch1", "kind": "InfraDevice", "actions": ["update"], "id": "obj-1"}],
            ),
        ):
            await run_generators.fn(model=model, context=MagicMock())

        artifact_calls = workflow_recorder.get_submit_calls_for(REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS)
        assert len(artifact_calls) == 0
        artifact_execute_calls = workflow_recorder.get_execute_calls_for(REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS)
        assert len(artifact_execute_calls) == 0

    @pytest.mark.anyio
    async def test_no_repo_check_dispatch_from_run_generators(self, workflow_recorder: WorkflowRecorder) -> None:
        """T015: Verify run_generators does not dispatch repository checks."""
        pipeline_id = uuid.uuid4()
        model = RequestProposedChangeRunGenerators(
            proposed_change="pc-1",
            source_branch="branch1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            branch_diff=_make_branch_diff(pipeline_id),
        )

        mock_client = AsyncMock()
        mock_client.filters = AsyncMock(return_value=[])

        with (
            patch("infrahub.proposed_change.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.proposed_change.tasks.get_client", return_value=mock_client),
            patch("infrahub.proposed_change.tasks.get_workflow", return_value=workflow_recorder),
            patch(
                "infrahub.proposed_change.tasks.get_diff_summary_cache",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await run_generators.fn(model=model, context=MagicMock())

        repo_calls = workflow_recorder.get_submit_calls_for(REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS)
        assert len(repo_calls) == 0
        repo_execute_calls = workflow_recorder.get_execute_calls_for(REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS)
        assert len(repo_execute_calls) == 0


class TestPipelineSequencing:
    """Tests for generator-before-artifact sequencing in run_proposed_change_pipeline()."""

    async def _run_pipeline(
        self, workflow_recorder: WorkflowRecorder, check_type: CheckType = CheckType.ALL
    ) -> WorkflowRecorder:
        """Helper to run the pipeline with mocked dependencies."""
        model = RequestProposedChangePipeline(
            proposed_change="pc-1",
            source_branch="branch1",
            source_branch_sync_with_git=True,
            destination_branch="main",
            check_type=check_type,
        )

        mock_client = AsyncMock()
        mock_client.get_diff_summary = AsyncMock(return_value=[])

        mock_dbs = AsyncMock()
        mock_db = AsyncMock()
        mock_db.start_session = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_dbs), __aexit__=AsyncMock())
        )

        mock_branch = MagicMock()
        mock_diff_coordinator = MagicMock()
        mock_diff_coordinator.set_logger = MagicMock()
        mock_diff_coordinator.update_branch_diff = AsyncMock()

        mock_component_registry = MagicMock()
        mock_component_registry.get_component = AsyncMock(return_value=mock_diff_coordinator)

        with (
            patch("infrahub.proposed_change.tasks.add_tags", new_callable=AsyncMock),
            patch("infrahub.proposed_change.tasks.get_client", return_value=mock_client),
            patch("infrahub.proposed_change.tasks.get_workflow", return_value=workflow_recorder),
            patch("infrahub.proposed_change.tasks.get_cache", new_callable=AsyncMock, return_value=AsyncMock()),
            patch("infrahub.proposed_change.tasks.get_database", new_callable=AsyncMock, return_value=mock_db),
            patch("infrahub.proposed_change.tasks.get_run_logger", return_value=MagicMock()),
            patch(
                "infrahub.proposed_change.tasks._get_proposed_change_repositories",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "infrahub.proposed_change.tasks._gather_repository_repository_diffs",
                new_callable=AsyncMock,
            ),
            patch(
                "infrahub.proposed_change.tasks._get_subscribers_from_diff",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "infrahub.proposed_change.tasks.set_diff_summary_cache",
                new_callable=AsyncMock,
            ),
            patch("infrahub.proposed_change.tasks.registry") as mock_registry,
            patch("infrahub.proposed_change.tasks.get_component_registry", return_value=mock_component_registry),
        ):
            mock_registry.get_branch = AsyncMock(return_value=mock_branch)

            await run_proposed_change_pipeline.fn(model=model, context=MagicMock())

        return workflow_recorder

    @pytest.mark.anyio
    async def test_pipeline_dispatches_artifacts_after_generators(self, workflow_recorder: WorkflowRecorder) -> None:
        """T016: Verify REFRESH_ARTIFACTS appears after RUN_GENERATORS in the call log."""
        recorder = await self._run_pipeline(workflow_recorder, check_type=CheckType.ALL)

        workflow_names = [c["workflow"].name for c in recorder.all_calls]

        # RUN_GENERATORS should be dispatched via execute_workflow
        assert REQUEST_PROPOSED_CHANGE_RUN_GENERATORS.name in workflow_names

        # REFRESH_ARTIFACTS should be dispatched via submit_workflow
        assert REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS.name in workflow_names

        gen_idx = workflow_names.index(REQUEST_PROPOSED_CHANGE_RUN_GENERATORS.name)
        art_idx = workflow_names.index(REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS.name)
        assert gen_idx < art_idx, f"Generators (index {gen_idx}) must complete before artifacts (index {art_idx})"

        # Generators via execute, artifacts via submit
        gen_call = recorder.all_calls[gen_idx]
        art_call = recorder.all_calls[art_idx]
        assert gen_call["type"] == "execute"
        assert art_call["type"] == "submit"

    @pytest.mark.anyio
    async def test_pipeline_generator_only_no_artifacts(self, workflow_recorder: WorkflowRecorder) -> None:
        """T017: For CheckType.GENERATOR, no artifact refresh should be dispatched."""
        recorder = await self._run_pipeline(workflow_recorder, check_type=CheckType.GENERATOR)

        workflow_names = [c["workflow"].name for c in recorder.all_calls]
        assert REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS.name not in workflow_names
        assert REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS.name not in workflow_names

    @pytest.mark.anyio
    async def test_pipeline_artifact_only_no_generators(self, workflow_recorder: WorkflowRecorder) -> None:
        """T018: For CheckType.ARTIFACT, artifact refresh is dispatched without generators."""
        recorder = await self._run_pipeline(workflow_recorder, check_type=CheckType.ARTIFACT)

        workflow_names = [c["workflow"].name for c in recorder.all_calls]
        assert REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS.name in workflow_names
        assert REQUEST_PROPOSED_CHANGE_RUN_GENERATORS.name not in workflow_names

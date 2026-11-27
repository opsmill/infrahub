from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.manager import NodeManager
from infrahub.database.validation import verify_graph
from infrahub.exceptions import ResourceNotFoundError, ValidationError
from infrahub.proposed_change.tasks import validate_artifacts_generation

from .test_failed_artifact_retry import DEFINITION_NAME, ArtifactRetryTestBase, RetryDataset

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


class TestArtifactRetryPreparation(ArtifactRetryTestBase):
    async def test_change_run_preparation_failure_invalidates_successful_validation(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, failed=False)
        model = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id, retry_failed_only=False)
        context = self._make_context(admin_account, default_branch)

        with pytest.raises(
            ResourceNotFoundError,
            match=re.escape(f"Diff summary for pipeline {model.branch_diff.pipeline_id} was not found in the cache"),
        ):
            await validate_artifacts_generation(model=model, context=context)

        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.QUEUED.value
        assert validator.conclusion.value.value == ValidatorConclusion.UNKNOWN.value
        assert not validator.started_at.value
        assert not validator.completed_at.value
        assert workflow_recorder.execute_calls == []

        with pytest.raises(
            ValidationError,
            match=rf"^The previous artifact checks of {DEFINITION_NAME} did not complete\. "
            r"Run the artifact checks again\.$",
        ):
            await validate_artifacts_generation(
                model=model.model_copy(update={"retry_failed_only": True}), context=context
            )

        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.QUEUED.value
        assert validator.conclusion.value.value == ValidatorConclusion.UNKNOWN.value
        assert workflow_recorder.execute_calls == []
        assert await self._check_conclusions(db=db, validator_id=history.validator_id) == history.conclusions
        await verify_graph(db=db, kinds=["CoreArtifactValidator", "CoreArtifactCheck"])

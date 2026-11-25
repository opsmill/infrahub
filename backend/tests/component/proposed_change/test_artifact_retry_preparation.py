from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.manager import NodeManager
from infrahub.database.validation import verify_graph
from infrahub.exceptions import ResourceNotFoundError, ValidationError
from infrahub.proposed_change.artifact_retry import ArtifactRetryRecords
from infrahub.proposed_change.tasks import validate_artifacts_generation

from .test_failed_artifact_retry import ArtifactRetryTestBase, RetryDataset

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder


class TestArtifactRetryPreparation(ArtifactRetryTestBase):
    async def test_ordinary_preparation_failure_invalidates_successful_validation(
        self,
        db: InfrahubDatabase,
        dataset: RetryDataset,
        memory_cache: MemoryCache,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        history = await self._history(db=db, dataset=dataset, memory_cache=memory_cache, failed=False)
        records = ArtifactRetryRecords(memory_cache)
        previous_record = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert previous_record is not None
        assert previous_record.completed is True
        assert previous_record.conclusion == ValidatorConclusion.SUCCESS
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
        interrupted_record = await records.get(
            proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
        )
        assert interrupted_record is not None
        assert interrupted_record.completed is False
        assert interrupted_record.completed_at is None
        assert interrupted_record.outcomes == history.outcomes
        assert workflow_recorder.execute_calls == []

        retry = self._request(dataset=dataset, proposed_change_id=history.proposed_change_id)
        with pytest.raises(ValidationError, match=re.escape("completed target history is missing or stale")):
            await validate_artifacts_generation(model=retry, context=context)

        validator = await NodeManager.get_one(db=db, id=history.validator_id, kind="CoreArtifactValidator")
        assert validator is not None
        assert validator.state.value.value == ValidatorState.QUEUED.value
        assert validator.conclusion.value.value == ValidatorConclusion.UNKNOWN.value
        assert not validator.started_at.value
        assert not validator.completed_at.value
        assert (
            await records.get(
                proposed_change_id=history.proposed_change_id, definition_id=dataset.definition.definition_id
            )
            == interrupted_record
        )
        assert workflow_recorder.execute_calls == []
        checks = await NodeManager.query(
            db=db, schema="CoreArtifactCheck", filters={"validator__ids": [history.validator_id]}
        )
        assert len(checks) == len(history.outcomes)
        assert {check.id: check.conclusion.value.value for check in checks} == {
            outcome.check_id: ValidatorConclusion.SUCCESS.value for outcome in history.outcomes.values()
        }
        await verify_graph(db=db, kinds=["CoreArtifactValidator", "CoreArtifactCheck"])

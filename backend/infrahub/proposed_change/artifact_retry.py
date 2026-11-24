from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from infrahub.artifacts.models import ArtifactCheckResult  # noqa: TC001  Pydantic resolves this field at runtime
from infrahub.core.constants import ValidatorConclusion, ValidatorState

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from infrahub.services.adapters.cache import InfrahubCache

ARTIFACT_RETRY_RECORD_TTL_SECONDS = 30 * 24 * 60 * 60


class ArtifactRetryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    validator_id: str
    completed_at: str | None = None
    completed: bool = False
    outcomes: dict[str, ArtifactCheckResult] = Field(default_factory=dict)

    @property
    def failed_target_ids(self) -> frozenset[str]:
        return frozenset(
            target_id
            for target_id, outcome in self.outcomes.items()
            if outcome.conclusion == ValidatorConclusion.FAILURE
        )

    @property
    def conclusion(self) -> ValidatorConclusion:
        if self.failed_target_ids:
            return ValidatorConclusion.FAILURE
        if any(outcome.conclusion == ValidatorConclusion.UNKNOWN for outcome in self.outcomes.values()):
            return ValidatorConclusion.UNKNOWN
        return ValidatorConclusion.SUCCESS

    def matches_validator(
        self, *, validator_id: str, completed_at: str | None, conclusion: str | None, state: str | None
    ) -> bool:
        return (
            self.completed
            and bool(self.completed_at)
            and self.validator_id == validator_id
            and self.completed_at == completed_at
            and state == ValidatorState.COMPLETED.value
            and self.conclusion.value == conclusion
            and all(outcome.conclusion != ValidatorConclusion.UNKNOWN for outcome in self.outcomes.values())
        )


def merge_artifact_outcomes(
    *,
    previous: Mapping[str, ArtifactCheckResult],
    updates: Mapping[str, ArtifactCheckResult],
    eligible_target_ids: Collection[str],
) -> dict[str, ArtifactCheckResult]:
    """Retain untouched eligible outcomes and replace the outcomes of attempted targets."""
    eligible = set(eligible_target_ids)
    return {
        target_id: outcome for target_id, outcome in (dict(previous) | dict(updates)).items() if target_id in eligible
    }


class ArtifactRetryRecords:
    """Store retry identities; callers serialize validation runs for each definition."""

    def __init__(self, cache: InfrahubCache) -> None:
        self._cache = cache

    async def get(self, *, proposed_change_id: str, definition_id: str) -> ArtifactRetryRecord | None:
        payload = await self._cache.get(
            key=self._key(proposed_change_id=proposed_change_id, definition_id=definition_id)
        )
        if not payload:
            return None
        try:
            return ArtifactRetryRecord.model_validate_json(payload)
        except ValidationError:
            return None

    async def start(self, *, proposed_change_id: str, definition_id: str, record: ArtifactRetryRecord) -> None:
        await self._save(
            proposed_change_id=proposed_change_id,
            definition_id=definition_id,
            record=record.model_copy(update={"completed": False, "completed_at": None}),
        )

    async def complete(
        self,
        *,
        proposed_change_id: str,
        definition_id: str,
        record: ArtifactRetryRecord,
        completed_at: str,
        outcomes: dict[str, ArtifactCheckResult],
    ) -> None:
        await self._save(
            proposed_change_id=proposed_change_id,
            definition_id=definition_id,
            record=record.model_copy(update={"completed": True, "completed_at": completed_at, "outcomes": outcomes}),
        )

    async def _save(self, *, proposed_change_id: str, definition_id: str, record: ArtifactRetryRecord) -> None:
        await self._cache.set(
            key=self._key(proposed_change_id=proposed_change_id, definition_id=definition_id),
            value=record.model_dump_json(),
            expires=ARTIFACT_RETRY_RECORD_TTL_SECONDS,
        )

    def _key(self, *, proposed_change_id: str, definition_id: str) -> str:
        return f"proposed_change:{proposed_change_id}:artifact_definition:{definition_id}:retry"

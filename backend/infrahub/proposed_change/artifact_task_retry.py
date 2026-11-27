from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import pydantic

from infrahub.artifacts.checks import artifact_check_name
from infrahub.core.constants import CheckType, ValidatorConclusion, ValidatorState
from infrahub.core.protocols import CoreArtifactCheck, CoreArtifactValidator
from infrahub.exceptions import ValidationError
from infrahub.proposed_change.artifact_retry import UNRESOLVED_CHECK_CONCLUSIONS
from infrahub.proposed_change.check_run import CheckRunRequest
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE, REQUEST_ARTIFACT_DEFINITION_CHECK

if TYPE_CHECKING:
    from infrahub.core.manager import NodeManager
    from infrahub.database import InfrahubDatabase

RUN_CHECKS_AGAIN = "Run the artifact checks of the proposed change again."


class ArtifactTargetRun(pydantic.BaseModel):
    """The parameters of a run that checks one artifact target, as far as they identify its validator and check."""

    validator_id: str
    check_id: str | None = None
    artifact_id: str | None = None
    artifact_name: str
    target_name: str


class ArtifactDefinitionReference(pydantic.BaseModel):
    definition_id: str


class ArtifactDefinitionRun(pydantic.BaseModel):
    """The parameters of a run that checks the targets of one artifact definition, as far as they identify its validator."""

    proposed_change: str
    artifact_definition: ArtifactDefinitionReference


class ArtifactTaskRetryResolver(ABC):
    """Resolves a finished artifact check task to the failed-only check run that retries it."""

    def __init__(self, db: InfrahubDatabase, node_manager: type[NodeManager]) -> None:
        self.db = db
        self.node_manager = node_manager

    @property
    @abstractmethod
    def workflow_name(self) -> str:
        """The name of the workflow whose runs this resolver reads."""

    @abstractmethod
    async def resolve(self, parameters: dict[str, Any]) -> CheckRunRequest:
        """Return the check run that retries what the task left failed or unfinished.

        Args:
            parameters: The parameters stored with the task's run.

        Raises:
            ValidationError: When the validator or the check of the task is not found, when the checks of the
                validator are not complete, or when nothing is left to retry.

        """

    def _read_run[RunT: pydantic.BaseModel](self, run_type: type[RunT], parameters: dict[str, Any]) -> RunT:
        try:
            return run_type.model_validate(parameters.get("model"))
        except pydantic.ValidationError:
            raise ValidationError(
                f"The parameters stored for this task do not identify its artifact validator. {RUN_CHECKS_AGAIN}"
            ) from None

    def _require_failed_validator(self, validator: CoreArtifactValidator) -> None:
        state = validator.state.value.value
        if state != ValidatorState.COMPLETED.value:
            raise ValidationError(
                f"The artifact checks of this task's validator are not complete (state: {state}). "
                "If they are still running, retry after they finish. "
                "Otherwise, run the artifact checks of the proposed change again."
            )
        if validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value:
            raise ValidationError("The artifact checks of this task's validator passed, so there is nothing to retry.")


class ArtifactTargetTaskRetryResolver(ArtifactTaskRetryResolver):
    """Resolves the task that checked one artifact target to a retry limited to the checks of that target.

    The check is the one the run names, else the validator's check of the same artifact, else its checks of the
    same name.
    """

    @property
    def workflow_name(self) -> str:
        return GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE.name

    async def resolve(self, parameters: dict[str, Any]) -> CheckRunRequest:
        run = self._read_run(run_type=ArtifactTargetRun, parameters=parameters)
        validators = await self.node_manager.query(
            db=self.db, schema=CoreArtifactValidator, filters={"ids": [run.validator_id]}
        )
        if not validators:
            raise ValidationError(f"The artifact validator of this task was not found. {RUN_CHECKS_AGAIN}")
        validator = validators[0]

        checks = await self._find_checks(validator_id=validator.id, run=run)
        if not checks:
            raise ValidationError(f"The artifact check of this task was not found. {RUN_CHECKS_AGAIN}")
        unresolved_check_ids = [
            check.id for check in checks if check.conclusion.value.value in UNRESOLVED_CHECK_CONCLUSIONS
        ]
        if not unresolved_check_ids:
            check_name = artifact_check_name(artifact_name=run.artifact_name, target_name=run.target_name)
            raise ValidationError(f"The artifact check '{check_name}' passed, so there is nothing to retry.")
        self._require_failed_validator(validator=validator)

        proposed_change = await validator.proposed_change.get_peer(db=self.db)
        if proposed_change is None:
            raise ValidationError("The proposed change of this task was not found.")
        return CheckRunRequest(
            proposed_change=proposed_change.id,
            check_type=CheckType.ARTIFACT,
            retry_failed_only=True,
            validator_id=validator.id,
            check_ids=unresolved_check_ids,
        )

    async def _find_checks(self, validator_id: str, run: ArtifactTargetRun) -> list[CoreArtifactCheck]:
        if run.check_id is not None:
            return await self._query_checks(filters={"ids": [run.check_id], "validator__ids": [validator_id]})
        if run.artifact_id is not None:
            checks = await self._query_checks(
                filters={"validator__ids": [validator_id], "artifact_id__value": run.artifact_id}
            )
            if checks:
                return checks
        return await self._query_checks(
            filters={
                "validator__ids": [validator_id],
                "name__value": artifact_check_name(artifact_name=run.artifact_name, target_name=run.target_name),
            }
        )

    async def _query_checks(self, filters: dict[str, Any]) -> list[CoreArtifactCheck]:
        return await self.node_manager.query(db=self.db, schema=CoreArtifactCheck, filters=filters)


class ArtifactDefinitionTaskRetryResolver(ArtifactTaskRetryResolver):
    """Resolves the task that checked the targets of one artifact definition to a retry of that definition's validator."""

    @property
    def workflow_name(self) -> str:
        return REQUEST_ARTIFACT_DEFINITION_CHECK.name

    async def resolve(self, parameters: dict[str, Any]) -> CheckRunRequest:
        run = self._read_run(run_type=ArtifactDefinitionRun, parameters=parameters)
        validators = await self.node_manager.query(
            db=self.db,
            schema=CoreArtifactValidator,
            filters={
                "proposed_change__ids": [run.proposed_change],
                "definition__ids": [run.artifact_definition.definition_id],
            },
        )
        if not validators:
            raise ValidationError(f"The artifact validator of this task was not found. {RUN_CHECKS_AGAIN}")
        validator = validators[0]
        self._require_failed_validator(validator=validator)

        unresolved_checks = await self.node_manager.count(
            db=self.db,
            schema=CoreArtifactCheck,
            filters={"validator__ids": [validator.id], "conclusion__values": list(UNRESOLVED_CHECK_CONCLUSIONS)},
        )
        if unresolved_checks == 0:
            raise ValidationError(
                f"No failed or unfinished artifact check was found for this task's validator. {RUN_CHECKS_AGAIN}"
            )
        return CheckRunRequest(
            proposed_change=run.proposed_change,
            check_type=CheckType.ARTIFACT,
            retry_failed_only=True,
            validator_id=validator.id,
        )

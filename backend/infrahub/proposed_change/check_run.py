from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import CheckType, InfrahubKind
from infrahub.core.protocols import CoreProposedChange
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.proposed_change.models import RequestProposedChangePipeline

if TYPE_CHECKING:
    from infrahub.core.manager import NodeManager
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class CheckRunRequest:
    """The checks of a proposed change that a caller asks to run."""

    proposed_change: str
    """The ID of the proposed change, or the value of its default filter."""

    check_type: CheckType = CheckType.ALL
    retry_failed_only: bool = False
    validator_id: str | None = None
    check_ids: list[str] | None = None


async def get_source_branch(db: InfrahubDatabase, name: str) -> Branch:
    """Return the source branch of a proposed change.

    Raises:
        ValidationError: When no branch has this name.

    """
    try:
        return await Branch.get_by_name(name=name, db=db)
    except BranchNotFoundError:
        raise ValidationError(
            input_value="The specified source branch for this proposed change was not found."
        ) from None


class CheckRunRequestBuilder:
    """Turns a request to run the checks of a proposed change into the request its pipeline takes."""

    def __init__(self, db: InfrahubDatabase, node_manager: type[NodeManager]) -> None:
        self.db = db
        self.node_manager = node_manager

    async def build(self, request: CheckRunRequest) -> RequestProposedChangePipeline:
        """Validate the request against the proposed change and return the pipeline request.

        Raises:
            ValidationError: When the selection of checks is inconsistent, the proposed change is not open, or
                the selected validator or checks do not belong to it.

        """
        check_ids = self._validate_selection(request=request)

        proposed_change = await self.node_manager.get_one_by_id_or_default_filter(
            id=request.proposed_change, kind=CoreProposedChange, db=self.db
        )
        state = ProposedChangeState(proposed_change.state.value.value)
        state.validate_state_check_run()

        if request.validator_id is not None:
            await self._validate_ownership(
                proposed_change_id=proposed_change.id, validator_id=request.validator_id, check_ids=check_ids
            )

        source_branch = await get_source_branch(db=self.db, name=proposed_change.source_branch.value)
        return RequestProposedChangePipeline(
            proposed_change=proposed_change.id,
            source_branch=source_branch.name,
            source_branch_sync_with_git=source_branch.sync_with_git,
            destination_branch=proposed_change.destination_branch.value,
            check_type=request.check_type,
            retry_failed_only=request.retry_failed_only,
            validator_id=request.validator_id,
            check_ids=check_ids,
        )

    def _validate_selection(self, request: CheckRunRequest) -> list[str] | None:
        if request.retry_failed_only and request.check_type != CheckType.ARTIFACT:
            raise ValidationError("retry_failed_only requires check_type ARTIFACT")
        validator_id = request.validator_id
        check_ids = request.check_ids
        if (validator_id is not None or check_ids is not None) and request.check_type != CheckType.ARTIFACT:
            raise ValidationError("validator_id and check_ids require check_type ARTIFACT")
        if validator_id is not None and not validator_id.strip():
            raise ValidationError("validator_id must not be blank")
        if check_ids is None:
            return None
        if validator_id is None:
            raise ValidationError("check_ids requires validator_id")
        if not check_ids or any(not check_id.strip() for check_id in check_ids):
            raise ValidationError("check_ids must not be empty or contain blank IDs")
        return list(dict.fromkeys(check_ids))

    async def _validate_ownership(
        self, proposed_change_id: str, validator_id: str, check_ids: list[str] | None
    ) -> None:
        validators = await self.node_manager.query(
            db=self.db,
            schema=InfrahubKind.ARTIFACTVALIDATOR,
            filters={"ids": [validator_id], "proposed_change__ids": [proposed_change_id]},
        )
        if not validators:
            raise ValidationError("validator_id must identify an artifact validator belonging to this proposed change")
        if check_ids is None:
            return
        checks = await self.node_manager.query(
            db=self.db,
            schema=InfrahubKind.ARTIFACTCHECK,
            filters={"ids": check_ids, "validator__ids": [validator_id]},
        )
        if {check.id for check in checks} != set(check_ids):
            raise ValidationError("check_ids must identify artifact checks belonging to the selected validator")

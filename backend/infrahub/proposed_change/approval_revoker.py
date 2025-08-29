import logging
from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.database import InfrahubDatabase

log = logging.getLogger(__name__)


class ApprovalRevoker(ABC):
    @abstractmethod
    async def revoke_approvals_on_updated_pcs(
        self,
        db: InfrahubDatabase,
        proposed_changes_ids: list[str] | None,
    ) -> None:
        raise NotImplementedError()


class ApprovalRevokerCommunity(ApprovalRevoker):
    async def revoke_approvals_on_updated_pcs(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        proposed_changes_ids: list[str] | None,  # noqa: ARG002
    ) -> None:
        raise ValueError("Revoking existing approvals based on branch changes is an enterprise feature.")


def get_approval_revoker() -> ApprovalRevoker:
    return ApprovalRevokerCommunity()


@inject
async def do_revoke_approvals_on_updated_pcs(
    db: InfrahubDatabase,
    proposed_changes_ids: list[str] | None = None,
    approval_revoker: ApprovalRevoker = Depends(get_approval_revoker),  # noqa: B008
) -> None:
    await approval_revoker.revoke_approvals_on_updated_pcs(db=db, proposed_changes_ids=proposed_changes_ids)

import logging
from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.database import InfrahubDatabase

log = logging.getLogger(__name__)


class ApprovalRevoker(ABC):
    @abstractmethod
    async def revoke_approvals_on_updated_pcs(self, db: InfrahubDatabase) -> None:
        raise NotImplementedError()


class ApprovalRevokerCommunity(ApprovalRevoker):
    async def revoke_approvals_on_updated_pcs(self, db: InfrahubDatabase) -> None:  # noqa: ARG002
        raise ValueError("Revoking existing approvals based on branch changes is an enterprise feature.")


def get_approval_revoker() -> ApprovalRevoker:
    return ApprovalRevokerCommunity()


@inject
async def do_revoke_approvals_on_all_pcs(
    db: InfrahubDatabase,
    approval_revoker: ApprovalRevoker = Depends(get_approval_revoker),  # noqa: B008
) -> None:
    return await approval_revoker.revoke_approvals_on_updated_pcs(db=db)

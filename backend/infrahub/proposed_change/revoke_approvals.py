import logging
from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

log = logging.getLogger(__name__)


class ApprovalRevoker(ABC):
    @abstractmethod
    async def revoke_approvals_on_updated_pcs(self, db: InfrahubDatabase) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def check_pc_has_enough_approvals(
        self, nb_approvals_required: int, proposed_change: Node, db: InfrahubDatabase
    ) -> str | None:
        raise NotImplementedError()


class ApprovalRevokerCommunity(ApprovalRevoker):
    async def check_pc_has_enough_approvals(
        self,
        nb_approvals_required: int,  # noqa: ARG002
        proposed_change: Node,  # noqa: ARG002
        db: InfrahubDatabase,  # noqa: ARG002
    ) -> str | None:
        raise ValueError("Revoking existing approvals based on branch changes is an enterprise feature.")

    async def revoke_approvals_on_updated_pcs(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
    ) -> None:
        raise ValueError("Revoking existing approvals based on branch changes is an enterprise feature.")


def get_approval_revoker() -> ApprovalRevoker:
    return ApprovalRevokerCommunity()


# TODO if we use CoreProposedChange instead of Node, pydantic is called through fast_depends @inject and raises an error
#  as we are using a Node as argument.
@inject
async def do_check_pc_has_enough_approvals(
    nb_approvals_required: int,
    proposed_change: Node,
    db: InfrahubDatabase,
    approval_revoker: ApprovalRevoker = Depends(get_approval_revoker),  # noqa: B008
) -> str | None:
    return await approval_revoker.check_pc_has_enough_approvals(
        nb_approvals_required=nb_approvals_required, proposed_change=proposed_change, db=db
    )


@inject
async def do_revoke_approvals_on_all_pcs(
    db: InfrahubDatabase,
    approval_revoker: ApprovalRevoker = Depends(get_approval_revoker),  # noqa: B008
) -> None:
    return await approval_revoker.revoke_approvals_on_updated_pcs(db=db)

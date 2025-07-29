from abc import ABC, abstractmethod

from fast_depends import Depends, inject

from infrahub.core.protocols import CoreProposedChange
from infrahub.database import InfrahubDatabase


class ProposedChangeChecker(ABC):
    @abstractmethod
    async def can_merge_proposed_change(self, proposed_change: CoreProposedChange, db: InfrahubDatabase) -> str | None:
        """
        Returns None if proposed change cannot be merged, otherwise returns the error message.
        """

        raise NotImplementedError()


class ProposedChangeCheckerCommunity(ProposedChangeChecker):
    async def can_merge_proposed_change(self, proposed_change: CoreProposedChange, db: InfrahubDatabase) -> str | None:  # noqa: ARG002
        return None


def get_proposed_change_merger() -> ProposedChangeChecker:
    return ProposedChangeCheckerCommunity()


# TODO if we use CoreProposedChange instead of Node, pydantic is called through fast_depends @inject and raises an error
#  as we are using a Node as argument.
@inject
async def can_merge_proposed_change(
    proposed_change: CoreProposedChange,
    db: InfrahubDatabase,
    pc_checker: ProposedChangeChecker = Depends(get_proposed_change_merger),  # noqa: B008
) -> str | None:
    # type ignore due to fast-depends enforcing pydantic checks
    return await pc_checker.can_merge_proposed_change(proposed_change=proposed_change, db=db)  # type: ignore

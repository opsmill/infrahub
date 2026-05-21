from infrahub_sdk.context import ContextAccount, RequestContext
from pydantic import BaseModel
from typing_extensions import Self

from infrahub.auth.session import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.events.models import EventBranchContext, EventContext


class BranchContext(BaseModel):
    name: str
    id: str | None = None

    @property
    def is_global(self) -> bool:
        return self.name == GLOBAL_BRANCH_NAME


class InfrahubContext(BaseModel):
    branch: BranchContext
    account: AccountSession

    @classmethod
    def init(cls, branch: Branch, account: AccountSession) -> Self:
        return cls(branch=BranchContext(name=branch.name, id=str(branch.uuid)), account=account)

    def to_event_context(self) -> EventContext:
        return EventContext(
            branch=EventBranchContext(name=self.branch.name, id=self.branch.id),
            account_id=self.account.account_id,
        )

    def to_request_context(self) -> RequestContext:
        return RequestContext(account=ContextAccount(id=self.account.account_id))

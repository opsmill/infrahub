from typing import Any

from infrahub_sdk.context import ContextAccount, RequestContext
from pydantic import BaseModel, Field
from typing_extensions import Self

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME


class ParentEvent(BaseModel):
    id: str
    name: str


class EventContext(BaseModel):
    name: str = Field(..., description="The name of the event")
    id: str = Field(..., description="The ID of the event")
    parent_id: str | None = Field(default=None)
    ancestors: list[ParentEvent] = Field(default_factory=list)


class BranchContext(BaseModel):
    name: str
    id: str | None = None

    @property
    def is_global(self) -> bool:
        return self.name == GLOBAL_BRANCH_NAME


class InfrahubContext(BaseModel):
    branch: BranchContext
    account: AccountSession
    event: EventContext | None = Field(default=None)

    @classmethod
    def init(cls, branch: Branch, account: AccountSession) -> Self:
        return cls(branch=BranchContext(name=branch.name, id=str(branch.uuid)), account=account)

    def set_event(self, name: str, id: str) -> None:
        if self.event:
            self.event.name = name
            self.event.id = id
        else:
            self.event = EventContext(name=name, id=id)

    def to_event(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def to_request_context(self) -> RequestContext:
        return RequestContext(account=ContextAccount(id=self.account.account_id))

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from infrahub import config
from infrahub.exceptions import RPCError
from infrahub.log import set_log_data


class Meta(BaseModel):
    request_id: str = ""
    correlation_id: str | None = Field(default=None)
    reply_to: str | None = Field(default=None)
    initiator_id: str | None = Field(
        default=None, description="The worker identity of the initial sender of this message"
    )
    retry_count: int | None = Field(default=None, description="Indicates how many times this message has been retried.")
    headers: dict[str, Any] | None = Field(default=None)
    validator_execution_id: str | None = Field(
        default=None, description="Validator execution ID related to this message"
    )
    check_execution_id: str | None = Field(default=None, description="Check execution ID related to this message")
    priority: int = Field(default=3, description="Message Priority")
    expiration: int | None = Field(default=None, description="TTL before this message expires in seconds")

    @classmethod
    def default(cls) -> Meta:
        return cls()


class InfrahubMessage(BaseModel):
    """Base Model for messages"""

    meta: Meta = Field(default_factory=Meta.default, description="Meta properties for the message")

    def assign_meta(self, parent: InfrahubMessage) -> None:
        """Assign relevant meta properties from a parent message."""
        self.meta.request_id = parent.meta.request_id
        self.meta.initiator_id = parent.meta.initiator_id

    def assign_header(self, key: str, value: Any) -> None:
        self.meta.headers = self.meta.headers or {}
        self.meta.headers[key] = value

    def assign_priority(self, priority: int) -> None:
        self.meta.priority = priority

    def assign_expiration(self, expiration: int) -> None:
        self.meta.expiration = expiration

    def set_log_data(self, routing_key: str) -> None:
        set_log_data(key="routing_key", value=routing_key)
        if self.meta.request_id:
            set_log_data(key="request_id", value=self.meta.request_id)

    @property
    def reply_requested(self) -> bool:
        if self.meta.reply_to:
            return True
        return False

    @property
    def body(self) -> bytes:
        return self.model_dump_json(
            exclude={"meta": {"headers", "priority", "expiration"}, "value": True}, exclude_none=True
        ).encode("UTF-8")

    def increase_retry_count(self, count: int = 1) -> None:
        current_retry = self.meta.retry_count or 0
        self.meta.retry_count = current_retry + count

    @property
    def reached_max_retries(self) -> bool:
        if self.meta and self.meta.retry_count:
            return self.meta.retry_count >= config.SETTINGS.broker.maximum_message_retries
        return False


class InfrahubResponseData(BaseModel):
    pass


class InfrahubResponse(InfrahubMessage):
    """A response to an RPC request"""

    passed: bool = True
    routing_key: str
    data: dict | InfrahubResponseData = Field(default_factory=dict)  # type: ignore[arg-type]
    errors: list[str] = Field(default_factory=list)
    initial_message: dict | None = Field(
        default=None,
        description="Initial message in dict format, the primary goal of this field is to provide additional context when there is an error",
    )

    def raise_for_status(self) -> None:
        if self.passed:
            return

        raise RPCError(message=", ".join(self.errors or ["Unknown Error"]))


class RPCErrorResponse(InfrahubResponse):
    passed: bool = False
    routing_key: str = "rpc_error"

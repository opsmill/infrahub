from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.timestamp import Timestamp
from infrahub.events.utils import get_all_infrahub_node_kind_events
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import EventTrigger, ExecuteWorkflow, TriggerDefinition, TriggerType
from infrahub.workflows.catalogue import WEBHOOK_PROCESS

if TYPE_CHECKING:
    from httpx import Response
    from infrahub_sdk.protocols import CoreCustomWebhook, CoreStandardWebhook, CoreTransformPython, CoreWebhook

    from infrahub.core.protocols import CoreWebhook as CoreWebhookNode
    from infrahub.services import InfrahubServices


class WebhookTriggerDefinition(TriggerDefinition):
    id: str
    type: TriggerType = TriggerType.WEBHOOK

    def generate_name(self) -> str:
        return f"{self.type.value}{NAME_SEPARATOR}{self.id}"

    @classmethod
    def generate_name_from_id(cls, id: str) -> str:
        return f"{TriggerType.WEBHOOK.value}{NAME_SEPARATOR}{id}"

    @classmethod
    def from_object(cls, obj: CoreWebhook | CoreWebhookNode) -> Self:
        event_trigger = EventTrigger()
        if obj.event_type.value == "all":
            event_trigger.events.add("infrahub.*")
        else:
            event_trigger.events.add(obj.event_type.value)

        if obj.branch_scope.value == "default_branch":
            event_trigger.match_related = {
                "prefect.resource.role": "infrahub.branch",
                "infrahub.resource.label": registry.default_branch,
            }
        elif obj.branch_scope.value == "other_branches":
            event_trigger.match_related = {
                "prefect.resource.role": "infrahub.branch",
                "infrahub.resource.label": f"!{registry.default_branch}",
            }

        if obj.node_kind.value and obj.event_type.value in get_all_infrahub_node_kind_events():
            event_trigger.match = {"infrahub.node.kind": obj.node_kind.value}

        definition = cls(
            id=obj.id,
            name=obj.name.value,
            trigger=event_trigger,
            actions=[
                ExecuteWorkflow(
                    workflow=WEBHOOK_PROCESS,
                    parameters={
                        "webhook_id": obj.id,
                        "webhook_name": obj.name.value,
                        "webhook_kind": obj.get_kind(),
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                        "event_id": "{{ event.id }}",
                        "event_type": "{{ event.event }}",
                        "event_occured_at": "{{ event.occurred }}",
                        "event_payload": {
                            "__prefect_kind": "json",
                            "value": {"__prefect_kind": "jinja", "template": "{{ event.payload | tojson }}"},
                        },
                    },
                ),
            ],
        )

        return definition


class EventContext(BaseModel):
    id: str = Field(..., description="The internal id of the event")
    branch: str | None = Field(None, description="The branch associated with the event")
    account_id: str | None = Field(None, description="The id of the account associated with the event")
    occured_at: str = Field(..., description="The time when the event occurred")
    event: str = Field(..., description="The event type")

    @classmethod
    def from_event(cls, event_id: str, event_type: str, event_occured_at: str, event_payload: dict[str, Any]) -> Self:
        """Extract the context from the raw event we are getting from Prefect."""

        infrahub_context: dict[str, Any] = event_payload.get("context", {})
        account_info: dict[str, Any] = infrahub_context.get("account", {})
        branch_info: dict[str, Any] = infrahub_context.get("branch", {})

        return cls(
            id=event_id,
            branch=branch_info.get("name")
            if branch_info and branch_info.get("name") != registry.get_global_branch().name
            else None,
            account_id=account_info.get("account_id"),
            occured_at=event_occured_at,
            event=event_type,
        )


class Webhook(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(...)
    url: str = Field(...)
    event_type: str = Field(...)
    validate_certificates: bool = Field(...)
    _payload: Any = None
    _headers: dict[str, Any] | None = None

    async def _prepare_payload(self, data: dict[str, Any], context: EventContext, service: InfrahubServices) -> None:  # noqa: ARG002
        self._payload = {"data": data, **context.model_dump()}

    def _assign_headers(self) -> None:
        self._headers = {}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def webhook_type(self) -> str:
        return self.__class__.__name__

    async def prepare(self, data: dict[str, Any], context: EventContext, service: InfrahubServices) -> None:
        await self._prepare_payload(data=data, context=context, service=service)
        self._assign_headers()

    async def send(self, data: dict[str, Any], context: EventContext, service: InfrahubServices) -> Response:
        await self.prepare(data=data, context=context, service=service)
        return await service.http.post(url=self.url, json=self.get_payload(), headers=self._headers)

    def get_payload(self) -> dict[str, Any]:
        return self._payload

    def to_cache(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_cache(cls, data: dict[str, Any]) -> Self:
        return cls(**data)


class CustomWebhook(Webhook):
    """Custom webhook"""

    @classmethod
    def from_object(cls, obj: CoreCustomWebhook) -> Self:
        return cls(
            name=obj.name.value,
            url=obj.url.value,
            event_type=obj.event_type.value,
            validate_certificates=obj.validate_certificates.value or False,
        )


class StandardWebhook(Webhook):
    shared_key: str = Field(...)

    def _assign_headers(self, uuid: UUID | None = None, at: Timestamp | None = None) -> None:
        message_id = f"msg_{uuid.hex}" if uuid else f"msg_{uuid4().hex}"
        timestamp = str(at.to_timestamp()) if at else str(Timestamp().to_timestamp())
        payload = json.dumps(self._payload or {})
        unsigned_data = f"{message_id}.{timestamp}.{payload}".encode()
        signature = self._sign(data=unsigned_data)

        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "webhook-id": message_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": f"v1,{base64.b64encode(signature).decode('utf-8')}",
        }

    def _sign(self, data: bytes) -> bytes:
        return hmac.new(key=self.shared_key.encode(), msg=data, digestmod=hashlib.sha256).digest()

    @classmethod
    def from_object(cls, obj: CoreStandardWebhook) -> Self:
        return cls(
            name=obj.name.value,
            url=obj.url.value,
            event_type=obj.event_type.value,
            validate_certificates=obj.validate_certificates.value or False,
            shared_key=obj.shared_key.value,
        )


class TransformWebhook(Webhook):
    repository_id: str = Field(...)
    repository_name: str = Field(...)
    repository_kind: str = Field(...)
    transform_name: str = Field(...)
    transform_class: str = Field(...)
    transform_file: str = Field(...)
    transform_timeout: int = Field(...)
    convert_query_response: bool = Field(...)

    async def _prepare_payload(self, data: dict[str, Any], context: EventContext, service: InfrahubServices) -> None:
        repo: InfrahubReadOnlyRepository | InfrahubRepository
        if self.repository_kind == InfrahubKind.READONLYREPOSITORY:
            repo = await InfrahubReadOnlyRepository.init(
                id=self.repository_id,
                name=self.repository_name,
                client=service.client,
                service=service,
            )
        else:
            repo = await InfrahubRepository.init(
                id=self.repository_id,
                name=self.repository_name,
                client=service.client,
                service=service,
            )

        branch = context.branch or repo.default_branch
        commit = repo.get_commit_value(branch_name=branch)

        self._payload = await repo.execute_python_transform.with_options(timeout_seconds=self.transform_timeout)(
            branch_name=branch,
            commit=commit,
            location=f"{self.transform_file}::{self.transform_class}",
            convert_query_response=self.convert_query_response,
            data={"data": data, **context.model_dump()},
            client=service.client,
        )  # type: ignore[misc]

    @classmethod
    def from_object(cls, obj: CoreCustomWebhook, transform: CoreTransformPython) -> Self:
        return cls(
            name=obj.name.value,
            url=obj.url.value,
            event_type=obj.event_type.value,
            validate_certificates=obj.validate_certificates.value or False,
            repository_id=transform.repository.id,
            repository_name=transform.repository.peer.name.value,
            repository_kind=transform.repository.peer.get_kind(),
            transform_name=transform.name.value,
            transform_class=transform.class_name.value,
            transform_file=transform.file_path.value,
            transform_timeout=transform.timeout.value,
            convert_query_response=transform.convert_query_response.value or False,
        )

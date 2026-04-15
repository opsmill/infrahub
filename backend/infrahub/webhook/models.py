from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from enum import StrEnum
from typing import TYPE_CHECKING, Any, assert_never
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing_extensions import Self

from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.timestamp import Timestamp
from infrahub.events.utils import get_all_infrahub_node_kind_events
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import EventTrigger, ExecuteWorkflow, TriggerDefinition, TriggerType
from infrahub.workflows.catalogue import WEBHOOK_PROCESS

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from httpx import Response
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.protocols import CoreCustomWebhook, CoreStandardWebhook, CoreTransformPython
    from prefect.automations import AutomationCore
    from prefect.client.orchestration import PrefectClient
    from prefect.events.schemas.automations import Automation

    from infrahub.core.protocols import CoreWebhook
    from infrahub.services.adapters.http import InfrahubHTTP


class WebhookTriggerDefinitionBuilder:
    """Builds a WebhookTriggerDefinition from a CoreWebhook."""

    def __init__(self, default_branch: str) -> None:
        self._default_branch = default_branch

    def build(self, webhook: CoreWebhook) -> WebhookTriggerDefinition:
        event_type = webhook.event_type.value.value
        branch_scope = webhook.branch_scope.value
        node_kind = webhook.node_kind.value
        webhook_id = webhook.id
        webhook_name = webhook.name.value
        webhook_kind = webhook.get_kind()

        event_trigger = EventTrigger()

        if event_type == "all":
            event_trigger.events.add("infrahub.*")
        else:
            event_trigger.events.add(event_type)

        if branch_scope == "default_branch":
            event_trigger.match_related = {
                "prefect.resource.role": "infrahub.branch",
                "infrahub.resource.label": self._default_branch,
            }
        elif branch_scope == "other_branches":
            event_trigger.match_related = {
                "prefect.resource.role": "infrahub.branch",
                "infrahub.resource.label": f"!{self._default_branch}",
            }

        if node_kind and event_type in get_all_infrahub_node_kind_events():
            event_trigger.match = {"infrahub.node.kind": node_kind}

        return WebhookTriggerDefinition(
            id=webhook_id,
            name=webhook_name,
            trigger=event_trigger,
            actions=[
                ExecuteWorkflow(
                    workflow=WEBHOOK_PROCESS,
                    parameters={
                        "webhook_id": webhook_id,
                        "webhook_name": webhook_name,
                        "webhook_kind": webhook_kind,
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


def generate_webhook_automation_name(webhook_id: str) -> str:
    return f"{TriggerType.WEBHOOK.value}{NAME_SEPARATOR}{webhook_id}"


class WebhookTriggerDefinition(TriggerDefinition):
    id: str
    type: TriggerType = TriggerType.WEBHOOK

    def generate_name(self) -> str:
        return generate_webhook_automation_name(self.id)


class WebhookAutomation:
    """A webhook's desired automation state in Prefect."""

    def __init__(self, trigger_definition: WebhookTriggerDefinition, active: bool) -> None:
        self._trigger_definition = trigger_definition
        self._active = active

    @property
    def name(self) -> str:
        return self._trigger_definition.generate_name()

    @property
    def webhook_id(self) -> str:
        return self._trigger_definition.id

    @property
    def active(self) -> bool:
        return self._active

    async def apply(self, client: PrefectClient) -> None:
        """Ensure Prefect matches desired state: create, update, or delete."""
        existing = await self._find_existing(client)

        if not self._active:
            if existing:
                await client.delete_automation(automation_id=existing.id)
                logger.info("Automation %s deleted (webhook disabled)", self.name)
            else:
                logger.info("Webhook %s is disabled, no automation to delete", self.name)
            return

        automation = await self._as_prefect_automation(client)
        if existing:
            await client.update_automation(automation_id=existing.id, automation=automation)
            logger.info("Automation %s updated", self.name)
        else:
            await client.create_automation(automation=automation)
            logger.info("Automation %s created", self.name)

    async def _find_existing(self, client: PrefectClient) -> Automation | None:
        from infrahub.trigger.setup import gather_all_automations

        all_automations = await gather_all_automations(client=client)
        matches = [a for a in all_automations if a.name == self.name]
        return matches[0] if matches else None

    async def _as_prefect_automation(self, client: PrefectClient) -> AutomationCore:
        from prefect.automations import AutomationCore as _AutomationCore

        deployment_name = self._trigger_definition.get_deployment_names()[0]
        deployment = await client.read_deployment_by_name(name=f"{deployment_name}/{deployment_name}")
        return _AutomationCore(
            name=self.name,
            description=self._trigger_definition.get_description(),
            enabled=True,
            trigger=self._trigger_definition.trigger.get_prefect(),
            actions=[
                action.get(deployment.id)
                for action in self._trigger_definition.actions
                if isinstance(action, ExecuteWorkflow)
            ],
        )


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
            # We use `GLOBAL_BRANCH_NAME` constant instead of `registry.get_global_branch().name` to the flow from depending on the registry
            branch=branch_info.get("name") if branch_info and branch_info.get("name") != GLOBAL_BRANCH_NAME else None,
            account_id=account_info.get("account_id"),
            occured_at=event_occured_at,
            event=event_type,
        )


class HeaderKind(StrEnum):
    STATIC = "static"
    ENVIRONMENT = "environment"


class WebhookHeaderResolutionError(Exception):
    pass


class WebhookHeader(BaseModel):
    key: str
    value: str
    kind: HeaderKind

    def resolve(self) -> str:
        """Resolve the header value based on its kind.

        Raises WebhookHeaderResolutionError if the value cannot be resolved.
        """
        match self.kind:
            case HeaderKind.STATIC:
                return self.value
            case HeaderKind.ENVIRONMENT:
                resolved = os.environ.get(self.value)
                if resolved is None:
                    raise WebhookHeaderResolutionError(f"Environment variable '{self.value}' not found")
                return resolved
            case _:
                assert_never(self.kind)


class Webhook(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(...)
    url: str = Field(...)
    event_type: str = Field(...)
    validate_certificates: bool | None = Field(...)
    custom_headers: list[WebhookHeader] = Field(default_factory=list)
    _payload: Any = None
    _headers: dict[str, Any] | None = None
    shared_key: str | None = Field(default=None, description="Shared key for signing the webhook requests")

    async def _prepare_payload(self, data: dict[str, Any], context: EventContext, client: InfrahubClient) -> None:  # noqa: ARG002
        self._payload = {"data": data, **context.model_dump()}

    def _assign_headers(self, uuid: UUID | None = None, at: Timestamp | None = None) -> None:
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        seen_keys: set[str] = set()
        for header in self.custom_headers:
            if header.key in seen_keys:
                logger.warning(
                    "Webhook '%s': duplicate header key '%s', later value will overwrite earlier one",
                    self.name,
                    header.key,
                )
            seen_keys.add(header.key)
            try:
                self._headers[header.key] = header.resolve()
            except WebhookHeaderResolutionError as exc:
                logger.warning("Webhook '%s': %s, skipping header '%s'", self.name, exc, header.key)

        if self.shared_key:
            message_id = f"msg_{uuid.hex}" if uuid else f"msg_{uuid4().hex}"
            timestamp = str(at.to_timestamp()) if at else str(Timestamp().to_timestamp())
            payload = json.dumps(self._payload or {}, separators=(",", ":"))
            unsigned_data = f"{message_id}.{timestamp}.{payload}".encode()
            signature = self._sign(data=unsigned_data)
            self._headers["webhook-id"] = message_id
            self._headers["webhook-timestamp"] = timestamp
            self._headers["webhook-signature"] = f"v1,{base64.b64encode(signature).decode('utf-8')}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def webhook_type(self) -> str:
        return self.__class__.__name__

    @property
    def signing_key(self) -> str:
        """Return the signing key for the webhook."""
        if self.shared_key:
            return self.shared_key
        raise ValueError("Shared key is not set for the webhook")

    async def prepare(self, data: dict[str, Any], context: EventContext, client: InfrahubClient) -> None:
        await self._prepare_payload(data=data, context=context, client=client)
        self._assign_headers()

    async def send(
        self, data: dict[str, Any], context: EventContext, http_service: InfrahubHTTP, client: InfrahubClient
    ) -> Response:
        await self.prepare(data=data, context=context, client=client)
        return await http_service.post(
            url=self.url, json=self.get_payload(), headers=self._headers, verify=self.validate_certificates
        )

    def get_payload(self) -> dict[str, Any]:
        return self._payload

    def to_cache(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_cache(cls, data: dict[str, Any]) -> Self:
        return cls(**data)

    def _sign(self, data: bytes) -> bytes:
        return hmac.new(key=self.signing_key.encode(), msg=data, digestmod=hashlib.sha256).digest()


class CustomWebhook(Webhook):
    """Custom webhook"""

    @classmethod
    def from_object(cls, obj: CoreCustomWebhook, custom_headers: list[WebhookHeader] | None = None) -> Self:
        return cls(
            name=obj.name.value,
            url=obj.url.value,
            event_type=obj.event_type.value,
            validate_certificates=obj.validate_certificates.value or False,
            shared_key=obj.shared_key.value,
            custom_headers=custom_headers or [],
        )


class StandardWebhook(Webhook):
    @classmethod
    def from_object(cls, obj: CoreStandardWebhook, custom_headers: list[WebhookHeader] | None = None) -> Self:
        return cls(
            name=obj.name.value,
            url=obj.url.value,
            event_type=obj.event_type.value,
            validate_certificates=obj.validate_certificates.value or False,
            shared_key=obj.shared_key.value,
            custom_headers=custom_headers or [],
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

    async def _prepare_payload(self, data: dict[str, Any], context: EventContext, client: InfrahubClient) -> None:
        repo: InfrahubReadOnlyRepository | InfrahubRepository
        if self.repository_kind == InfrahubKind.READONLYREPOSITORY:
            repo = await InfrahubReadOnlyRepository.init(
                id=self.repository_id, name=self.repository_name, client=client
            )
        else:
            repo = await InfrahubRepository.init(id=self.repository_id, name=self.repository_name, client=client)

        branch = context.branch or repo.default_branch
        commit = repo.get_commit_value(branch_name=branch)

        self._payload = await repo.execute_python_transform.with_options(timeout_seconds=self.transform_timeout)(
            branch_name=branch,
            commit=commit,
            location=f"{self.transform_file}::{self.transform_class}",
            convert_query_response=self.convert_query_response,
            data={"data": {"data": data, **context.model_dump()}},
            client=client,
        )  # type: ignore[call-overload]

    @classmethod
    def from_object(
        cls, obj: CoreCustomWebhook, transform: CoreTransformPython, custom_headers: list[WebhookHeader] | None = None
    ) -> Self:
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
            shared_key=obj.shared_key.value,
            custom_headers=custom_headers or [],
        )

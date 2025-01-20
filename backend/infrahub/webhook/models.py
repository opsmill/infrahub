import base64
import hashlib
import hmac
from datetime import datetime, timezone
from math import floor
from typing import Any, Optional, Union
from uuid import uuid4

from infrahub_sdk.protocols import CoreTransformPython
from pydantic import BaseModel, ConfigDict, Field

from infrahub.core.constants import InfrahubKind
from infrahub.git.repository import InfrahubReadOnlyRepository, InfrahubRepository
from infrahub.services import InfrahubServices
from infrahub.transformations.constants import DEFAULT_TRANSFORM_TIMEOUT


class SendWebhookData(BaseModel):
    """Sent a webhook to an external source."""

    webhook_id: str = Field(..., description="The unique ID of the webhook")
    event_type: str = Field(..., description="The event type")
    event_data: dict = Field(..., description="The data tied to the event")


class Webhook(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    service: InfrahubServices = Field(...)
    url: str = Field(...)
    event_type: str = Field(...)
    data: dict[str, Any] = Field(...)
    validate_certificates: bool = Field(...)
    _payload: Any = None
    _headers: Optional[dict[str, Any]] = None

    async def _prepare_payload(self) -> None:
        self._payload = {"event_type": self.event_type, "data": self.data}

    def _assign_headers(self) -> None:
        self._headers = {}

    @property
    def webhook_type(self) -> str:
        return self.__class__.__name__

    async def send(self) -> None:
        await self._prepare_payload()
        self._assign_headers()
        await self.service.http.post(url=self.url, json=self._payload, headers=self._headers)


class CustomWebhook(Webhook):
    """Custom webhook"""


class StandardWebhook(Webhook):
    shared_key: bytes = Field(...)

    def _assign_headers(self) -> None:
        message_id = f"msg_{uuid4().hex}"
        timestamp = str(floor(datetime.now(tz=timezone.utc).timestamp()))
        payload = self._payload or {}
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
        return hmac.new(key=self.shared_key, msg=data, digestmod=hashlib.sha256).digest()


class TransformWebhook(Webhook):
    repository_id: str = Field(...)
    repository_name: str = Field(...)
    repository_kind: str = Field(...)
    transform_name: str = Field(...)
    transform_class: str = Field(...)
    transform_file: str = Field(...)

    async def _prepare_payload(self) -> None:
        repo: Union[InfrahubReadOnlyRepository, InfrahubRepository]
        if self.repository_kind == InfrahubKind.READONLYREPOSITORY:
            repo = await InfrahubReadOnlyRepository.init(
                id=self.repository_id, name=self.repository_name, client=self.service.client
            )
        else:
            repo = await InfrahubRepository.init(
                id=self.repository_id, name=self.repository_name, client=self.service.client
            )

        default_branch = repo.default_branch
        commit = repo.get_commit_value(branch_name=default_branch)

        timeout = DEFAULT_TRANSFORM_TIMEOUT
        if transform := await self.service.client.get(
            kind=CoreTransformPython, name__value=self.transform_name, raise_when_missing=False
        ):
            timeout = transform.timeout.value

        self._payload = await repo.execute_python_transform.with_options(timeout_seconds=timeout)(
            branch_name=default_branch,
            commit=commit,
            location=f"{self.transform_file}::{self.transform_class}",
            data={"event_type": self.event_type, "data": self.data},
            client=self.service.client,
        )

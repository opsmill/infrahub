"""Store the result an external engine returns for a render request."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Self

from infrahub_sdk.uuidt import UUIDT
from pydantic import BaseModel, Field, model_validator

from infrahub.artifacts.content import artifact_checksum, format_artifact_content
from infrahub.artifacts.render_lock import artifact_render_lock
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, ArtifactStatus
from infrahub.core.protocols import CoreArtifact, CoreArtifactDefinition, CoreArtifactTarget
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.models import EventBranchContext, EventContext, EventMeta
from infrahub.exceptions import (
    PermissionDeniedError,
    RenderRequestNotActiveError,
    RenderResultInvalidError,
    RenderResultTooLargeError,
)

if TYPE_CHECKING:
    from infrahub.artifacts.render_token import RenderTokenClaims
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.storage import InfrahubObjectStorage

RENDER_FAILURE_MESSAGE_MAX_LENGTH = 4096


RENDER_RESULT_SUCCESS = "success"
RENDER_RESULT_FAILURE = "failure"


class RenderResultPayload(BaseModel):
    status: Literal["success", "failure"]
    content: str | dict[str, Any] | None = Field(
        default=None, description="Rendered content, required when the status is success"
    )
    content_type: str | None = Field(
        default=None, description="When present, must equal the content type of the artifact definition"
    )
    message: str | None = Field(
        default=None,
        max_length=RENDER_FAILURE_MESSAGE_MAX_LENGTH,
        description="Why the render failed, required when the status is failure",
    )

    @model_validator(mode="after")
    def check_required_fields(self) -> Self:
        if self.status == RENDER_RESULT_SUCCESS and self.content is None:
            raise ValueError("content is required when status is success")
        if self.status == RENDER_RESULT_FAILURE and not self.message:
            raise ValueError("message is required when status is failure")
        return self


@dataclass(frozen=True)
class RenderResultOutcome:
    artifact_id: str
    branch: str
    status: ArtifactStatus
    message: str | None = None
    """The engine's failure message."""
    checksum: str | None = None
    storage_id: str | None = None
    changed: bool = False
    """Whether the stored content differs from the content before this render."""


def check_render_id(render_id: str, claims: RenderTokenClaims) -> None:
    """Refuse a token issued for another render request than the one in the request path.

    Raises:
        PermissionDeniedError: When the token's render ID differs from `render_id`.

    """
    if render_id != claims.render_id:
        raise PermissionDeniedError("The render token was issued for another render request")


class RenderResultAcceptor:
    """Store the result of an artifact's current render request and set the artifact Ready or Error.

    Writes are recorded as the system user because the engine authenticates with the render token, not an account.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        storage: InfrahubObjectStorage,
        event_service: InfrahubEventService,
        max_content_bytes: int,
    ) -> None:
        self.db = db
        self.storage = storage
        self.event_service = event_service
        self.max_content_bytes = max_content_bytes

    async def accept_render_result(
        self, render_id: str, claims: RenderTokenClaims, body: RenderResultPayload
    ) -> RenderResultOutcome:
        """Apply `body` to the artifact named in `claims` when `render_id` is still its current render request.

        Raises:
            PermissionDeniedError: When the token was issued for another render request.
            RenderResultInvalidError: When `content_type` differs from the artifact definition's.
            RenderResultTooLargeError: When the content is larger than `max_content_bytes`.
            RenderRequestNotActiveError: When the artifact is gone, or its render request was replaced or has ended.

        """
        check_render_id(render_id=render_id, claims=claims)
        branch = await registry.get_branch(db=self.db, branch=claims.branch)

        async with artifact_render_lock(branch=claims.branch, artifact_id=claims.artifact_id):
            artifact = await registry.manager.get_one(
                db=self.db, id=claims.artifact_id, branch=branch, kind=CoreArtifact
            )
            if artifact is None:
                raise RenderRequestNotActiveError()

            content: str | None = None
            content_type: str | None = None
            if body.status == RENDER_RESULT_SUCCESS:
                definition = await artifact.definition.get_peer(
                    db=self.db, peer_type=CoreArtifactDefinition, raise_on_error=True
                )
                content_type = str(definition.get_attribute("content_type").get_value())
                if body.content_type is not None and body.content_type != content_type:
                    raise RenderResultInvalidError(
                        f"content_type {body.content_type} does not match the artifact definition ({content_type})"
                    )
                content = format_artifact_content(content=body.content, content_type=content_type)
                size = len(content.encode("utf-8"))
                if size > self.max_content_bytes:
                    raise RenderResultTooLargeError(size=size, limit=self.max_content_bytes)

            if artifact.render_request_id.value != render_id or artifact.render_deadline.value is None:
                raise RenderRequestNotActiveError()

            if content is None or content_type is None:
                artifact.get_attribute("status").value = ArtifactStatus.ERROR.value
                artifact.render_deadline.value = None
                await artifact.save(db=self.db, user_id=SYSTEM_USER_ID)
                return RenderResultOutcome(
                    artifact_id=artifact.id, branch=branch.name, status=ArtifactStatus.ERROR, message=body.message
                )

            return await self._store_content(
                branch=branch, artifact=artifact, content=content, content_type=content_type
            )

    async def _store_content(
        self, branch: Branch, artifact: CoreArtifact, content: str, content_type: str
    ) -> RenderResultOutcome:
        checksum = artifact_checksum(content=content)
        previous_checksum = artifact.checksum.value
        previous_storage_id = artifact.storage_id.value
        changed = checksum != previous_checksum or not previous_storage_id

        storage_id = previous_storage_id
        if changed:
            storage_id = str(UUIDT())
            await asyncio.to_thread(
                self.storage.store, identifier=storage_id, content=io.BytesIO(content.encode("utf-8"))
            )

        artifact.get_attribute("status").value = ArtifactStatus.READY.value
        artifact.checksum.value = checksum
        artifact.storage_id.value = storage_id
        artifact.get_attribute("content_type").value = content_type
        artifact.render_deadline.value = None
        await artifact.save(db=self.db, user_id=SYSTEM_USER_ID)

        if changed and storage_id:
            target = await artifact.object.get_peer(db=self.db, peer_type=CoreArtifactTarget, raise_on_error=True)
            definition = await artifact.definition.get_peer(
                db=self.db, peer_type=CoreArtifactDefinition, raise_on_error=True
            )
            event_class = ArtifactUpdatedEvent if previous_checksum else ArtifactCreatedEvent
            await self.event_service.send(
                event=event_class(
                    node_id=artifact.id,
                    target_id=target.id,
                    target_kind=target.get_kind(),
                    artifact_definition_id=definition.id,
                    artifact_definition_name=definition.name.value,
                    checksum=checksum,
                    checksum_previous=previous_checksum,
                    storage_id=storage_id,
                    storage_id_previous=previous_storage_id,
                    meta=EventMeta.from_context(
                        context=EventContext(
                            branch=EventBranchContext(name=branch.name, id=str(branch.get_uuid())),
                            account_id=SYSTEM_USER_ID,
                        ),
                        branch=branch,
                    ),
                )
            )

        return RenderResultOutcome(
            artifact_id=artifact.id,
            branch=branch.name,
            status=ArtifactStatus.READY,
            checksum=checksum,
            storage_id=storage_id,
            changed=changed,
        )

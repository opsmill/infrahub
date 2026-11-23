"""Store the result an external engine returns for a render request."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, Self

from infrahub_sdk.uuidt import UUIDT
from pydantic import BaseModel, Field, model_validator

from infrahub.artifacts.content import artifact_checksum, format_artifact_content
from infrahub.artifacts.render_lock import artifact_render_lock
from infrahub.core import registry
from infrahub.core.constants import SYSTEM_USER_ID, ArtifactStatus, ContentType, Severity, ValidatorConclusion
from infrahub.core.protocols import (
    CoreArtifact,
    CoreArtifactCheck,
    CoreArtifactDefinition,
    CoreArtifactTarget,
    CoreProposedChange,
    CoreTransformation,
    CoreValidator,
)
from infrahub.core.validators.checks_runner import recompute_validator
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.models import EventBranchContext, EventContext, EventMeta
from infrahub.exceptions import (
    PermissionDeniedError,
    RenderRequestNotActiveError,
    RenderResultInvalidError,
    RenderResultTooLargeError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.artifacts.render_token import RenderTokenClaims, RenderTokenRequest
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.event import InfrahubEventService
    from infrahub.storage import InfrahubObjectStorage

RENDER_FAILURE_MESSAGE_MAX_LENGTH = 4096
STRUCTURED_CONTENT_TYPES = frozenset({ContentType.APPLICATION_JSON.value, ContentType.APPLICATION_YAML.value})


RENDER_SUCCEEDED_MESSAGE = "Artifact rendered successfully"
RENDER_FAILED_MESSAGE = "Failed to render artifact"
RENDER_UNDELIVERED_MESSAGE = "render request could not be delivered"
WAITING_FOR_EXTERNAL_ENGINE_MESSAGE = "waiting for external engine"

RENDER_RESULT_SUCCESS = "success"
RENDER_RESULT_FAILURE = "failure"
RENDER_RESULT_RUNNING = "running"


class RenderResultPayload(BaseModel):
    status: Literal["success", "failure", "running"] = Field(
        description="running reports progress: it moves the deadline and returns a new token"
    )
    content: str | dict[str, Any] | list[Any] | None = Field(
        default=None,
        description="Rendered content, required when the status is success; an object or a list only for JSON or YAML",
    )
    content_type: str | None = Field(
        default=None, description="When present, must equal the content type of the artifact definition"
    )
    message: str | None = Field(
        default=None,
        max_length=RENDER_FAILURE_MESSAGE_MAX_LENGTH,
        description="Why the render failed, required when the status is failure; the progress shown on the check when running",
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


class RenderProgressResponse(BaseModel):
    render_id: str
    deadline: datetime = Field(description="The new deadline of the render request")
    token: str = Field(description="Render token valid until the new deadline, to use for every later callback")


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

        # One transaction, so a reader never sees the artifact Ready with the checksum of the previous content.
        artifact_event: ArtifactCreatedEvent | ArtifactUpdatedEvent | None = None
        async with (
            artifact_render_lock(branch=claims.branch, artifact_id=claims.artifact_id),
            self.db.start_transaction() as db,
        ):
            artifact = await registry.manager.get_one(db=db, id=claims.artifact_id, branch=branch, kind=CoreArtifact)
            if artifact is None:
                raise RenderRequestNotActiveError()

            content: str | None = None
            content_type: str | None = None
            if body.status == RENDER_RESULT_SUCCESS:
                definition = await artifact.definition.get_peer(
                    db=db, peer_type=CoreArtifactDefinition, raise_on_error=True
                )
                content_type = str(definition.get_attribute("content_type").get_value())
                if body.content_type is not None and body.content_type != content_type:
                    raise RenderResultInvalidError(
                        f"content_type {body.content_type} does not match the artifact definition ({content_type})"
                    )
                if not isinstance(body.content, str) and content_type not in STRUCTURED_CONTENT_TYPES:
                    raise RenderResultInvalidError(
                        f"content must be a string for the content type of the artifact definition ({content_type})"
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
                await artifact.save(db=db, user_id=SYSTEM_USER_ID)
                outcome = RenderResultOutcome(
                    artifact_id=artifact.id, branch=branch.name, status=ArtifactStatus.ERROR, message=body.message
                )
            else:
                outcome, artifact_event = await self._store_content(
                    db=db, branch=branch, artifact=artifact, content=content, content_type=content_type
                )
            validator_ids = await conclude_waiting_checks(db=db, branch=branch, outcome=outcome)

        if artifact_event is not None:
            await self.event_service.send(event=artifact_event)

        for validator_id in validator_ids:
            await recompute_validator(
                db=self.db,
                event_service=self.event_service,
                validator_id=validator_id,
                context=system_event_context(branch=branch),
            )
        return outcome

    async def report_progress(self, render_id: str, claims: RenderTokenClaims, message: str | None) -> datetime:
        """Move the deadline of the artifact's current render request to now plus the transformation's timeout.

        The waiting proposed-change checks show `message`. Returns the new deadline.

        Raises:
            PermissionDeniedError: When the token was issued for another render request.
            RenderRequestNotActiveError: When the artifact is gone, or its render request was replaced or has ended.

        """
        check_render_id(render_id=render_id, claims=claims)
        branch = await registry.get_branch(db=self.db, branch=claims.branch)
        async with (
            artifact_render_lock(branch=claims.branch, artifact_id=claims.artifact_id),
            self.db.start_transaction() as db,
        ):
            artifact = await registry.manager.get_one(db=db, id=claims.artifact_id, branch=branch, kind=CoreArtifact)
            if (
                artifact is None
                or artifact.render_request_id.value != render_id
                or artifact.render_deadline.value is None
            ):
                raise RenderRequestNotActiveError()
            definition = await artifact.definition.get_peer(
                db=db, peer_type=CoreArtifactDefinition, raise_on_error=True
            )
            transformation = await definition.transformation.get_peer(
                db=db, peer_type=CoreTransformation, raise_on_error=True
            )
            deadline = datetime.now(UTC) + timedelta(seconds=int(transformation.timeout.value))
            artifact.render_deadline.value = deadline.isoformat()
            await artifact.save(db=db, user_id=SYSTEM_USER_ID)
            if message:
                for check, _ in await _waiting_checks(db=db, branch=branch, artifact_id=artifact.id):
                    check.message.value = f"{WAITING_FOR_EXTERNAL_ENGINE_MESSAGE}: {message}"
                    await check.save(db=db, user_id=SYSTEM_USER_ID)
        return deadline

    async def _store_content(
        self, db: InfrahubDatabase, branch: Branch, artifact: CoreArtifact, content: str, content_type: str
    ) -> tuple[RenderResultOutcome, ArtifactCreatedEvent | ArtifactUpdatedEvent | None]:
        """Store the content and set the artifact Ready, and return the event to send once the transaction commits."""
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
        await artifact.save(db=db, user_id=SYSTEM_USER_ID)

        event: ArtifactCreatedEvent | ArtifactUpdatedEvent | None = None
        if changed and storage_id:
            target = await artifact.object.get_peer(db=db, peer_type=CoreArtifactTarget, raise_on_error=True)
            definition = await artifact.definition.get_peer(
                db=db, peer_type=CoreArtifactDefinition, raise_on_error=True
            )
            event_class = ArtifactUpdatedEvent if previous_checksum else ArtifactCreatedEvent
            event = event_class(
                node_id=artifact.id,
                target_id=target.id,
                target_kind=target.get_kind(),
                artifact_definition_id=definition.id,
                artifact_definition_name=definition.name.value,
                checksum=checksum,
                checksum_previous=previous_checksum,
                storage_id=storage_id,
                storage_id_previous=previous_storage_id,
                meta=EventMeta.from_context(context=system_event_context(branch=branch), branch=branch),
            )

        outcome = RenderResultOutcome(
            artifact_id=artifact.id,
            branch=branch.name,
            status=ArtifactStatus.READY,
            checksum=checksum,
            storage_id=storage_id,
            changed=changed,
        )
        return outcome, event


async def fail_render(
    db: InfrahubDatabase,
    event_service: InfrahubEventService,
    branch: Branch,
    artifact_id: str,
    message: str,
    is_active: Callable[[CoreArtifact], bool],
) -> CoreArtifact | None:
    """Set the artifact to Error and fail the checks waiting for it, when `is_active` still holds under the render lock.

    Returns the artifact, or None when it is gone or its render request is no longer the one `is_active` expects.
    """
    async with artifact_render_lock(branch=branch.name, artifact_id=artifact_id), db.start_transaction() as dbt:
        artifact = await registry.manager.get_one(db=dbt, id=artifact_id, branch=branch, kind=CoreArtifact)
        if artifact is None or not is_active(artifact):
            return None
        artifact.get_attribute("status").value = ArtifactStatus.ERROR.value
        artifact.render_deadline.value = None
        await artifact.save(db=dbt, user_id=SYSTEM_USER_ID)
        outcome = RenderResultOutcome(
            artifact_id=artifact.id, branch=branch.name, status=ArtifactStatus.ERROR, message=message
        )
        validator_ids = await conclude_waiting_checks(db=dbt, branch=branch, outcome=outcome)

    for validator_id in validator_ids:
        await recompute_validator(
            db=db, event_service=event_service, validator_id=validator_id, context=system_event_context(branch=branch)
        )
    return artifact


async def fail_undelivered_render(
    db: InfrahubDatabase, event_service: InfrahubEventService, request: RenderTokenRequest, reason: str
) -> bool:
    """End a render request that could not be delivered to the engine, and return whether it was still active.

    A request that was replaced or already concluded is left as it is.
    """
    branch = await registry.get_branch(db=db, branch=request.branch)
    artifact = await fail_render(
        db=db,
        event_service=event_service,
        branch=branch,
        artifact_id=request.artifact_id,
        message=f"{RENDER_UNDELIVERED_MESSAGE}: {reason}",
        is_active=lambda candidate: (
            candidate.render_request_id.value == request.render_id and candidate.render_deadline.value is not None
        ),
    )
    return artifact is not None


async def conclude_waiting_checks(db: InfrahubDatabase, branch: Branch, outcome: RenderResultOutcome) -> set[str]:
    """Write the outcome to the proposed-change checks of this artifact that wait for it, and return their validators.

    A check waits when its conclusion is still unknown and its proposed change's source branch is the branch the
    artifact was rendered on.
    """
    validator_ids: set[str] = set()
    for check, validator in await _waiting_checks(db=db, branch=branch, artifact_id=outcome.artifact_id):
        if outcome.status == ArtifactStatus.READY:
            check.get_attribute("conclusion").value = ValidatorConclusion.SUCCESS.value
            check.get_attribute("severity").value = Severity.INFO.value
            check.message.value = RENDER_SUCCEEDED_MESSAGE
        else:
            check.get_attribute("conclusion").value = ValidatorConclusion.FAILURE.value
            check.get_attribute("severity").value = Severity.CRITICAL.value
            check.message.value = f"{RENDER_FAILED_MESSAGE}: {outcome.message}"
        check.changed.value = outcome.changed
        check.checksum.value = outcome.checksum
        check.storage_id.value = outcome.storage_id
        check.artifact_id.value = outcome.artifact_id
        await check.save(db=db, user_id=SYSTEM_USER_ID)
        validator_ids.add(validator.id)
    return validator_ids


async def _waiting_checks(
    db: InfrahubDatabase, branch: Branch, artifact_id: str
) -> list[tuple[CoreArtifactCheck, CoreValidator]]:
    """Return the proposed-change checks of the artifact still waiting for its render on `branch`, with their validators.

    A check waits when its conclusion is still unknown and its proposed change's source branch is `branch`.
    """
    checks = await registry.manager.query(
        db=db,
        schema=CoreArtifactCheck,
        filters={"artifact_id__value": artifact_id, "conclusion__value": ValidatorConclusion.UNKNOWN.value},
    )
    waiting: list[tuple[CoreArtifactCheck, CoreValidator]] = []
    for check in checks:
        validator = await check.validator.get_peer(db=db, peer_type=CoreValidator, raise_on_error=True)
        proposed_change = await validator.proposed_change.get_peer(
            db=db, peer_type=CoreProposedChange, raise_on_error=True
        )
        if proposed_change.source_branch.value == branch.name:
            waiting.append((check, validator))
    return waiting


def system_event_context(branch: Branch) -> EventContext:
    return EventContext(
        branch=EventBranchContext(name=branch.name, id=str(branch.get_uuid())), account_id=SYSTEM_USER_ID
    )

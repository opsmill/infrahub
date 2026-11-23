"""Set external renders that got no answer before their deadline to Error."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub_sdk.timestamp import Timestamp
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.artifacts.render_result import fail_render
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import ArtifactStatus
from infrahub.core.protocols import CoreArtifact, CoreArtifactDefinition, CoreTransformation
from infrahub.exceptions import NodeNotFoundError
from infrahub.log import get_logger
from infrahub.workers.dependencies import get_database, get_event_service

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.event import InfrahubEventService

RENDER_TIMEOUT_MESSAGE = "no response from engine"

log = get_logger()


@dataclass(frozen=True)
class RenderTimeout:
    artifact_id: str
    branch: str
    transformation_name: str | None


def _is_overdue(artifact: CoreArtifact, now: Timestamp) -> bool:
    deadline = artifact.render_deadline.value
    return (
        artifact.get_attribute("status").get_value() == ArtifactStatus.PENDING.value
        and deadline is not None
        and Timestamp(deadline) < now
    )


async def expire_overdue_renders(
    db: InfrahubDatabase, event_service: InfrahubEventService, now: Timestamp
) -> list[RenderTimeout]:
    """Set every pending artifact whose render deadline is before `now` to Error and fail the checks waiting for it."""
    branches = sorted(
        await Branch.get_list(db=db, limit=None, exclude_global=True, exclude_terminal=True),
        key=lambda branch: not branch.is_default,
    )
    # A branch reads the artifacts of the default branch it did not change, so a render request seen first on the
    # default branch belongs to it and must not be written again on every other branch.
    seen_requests: set[tuple[str, str | None]] = set()
    timeouts: list[RenderTimeout] = []
    for branch in branches:
        pending = await registry.manager.query(
            db=db, schema=CoreArtifact, branch=branch, filters={"status__value": ArtifactStatus.PENDING.value}
        )
        for candidate in pending:
            request = (candidate.id, candidate.render_request_id.value)
            if request in seen_requests:
                continue
            seen_requests.add(request)
            if not _is_overdue(artifact=candidate, now=now):
                continue
            # One artifact whose peers cannot be read must not stop the sweep of the others.
            try:
                timeout = await _expire_render(
                    db=db, event_service=event_service, branch=branch, artifact_id=candidate.id, now=now
                )
            except (LookupError, NodeNotFoundError):
                log.exception("Could not expire an overdue render", artifact_id=candidate.id, branch=branch.name)
                continue
            if timeout is not None:
                timeouts.append(timeout)
    return timeouts


async def _expire_render(
    db: InfrahubDatabase, event_service: InfrahubEventService, branch: Branch, artifact_id: str, now: Timestamp
) -> RenderTimeout | None:
    # The deadline is read again under the lock because a callback or a new request may have replaced it.
    artifact = await fail_render(
        db=db,
        event_service=event_service,
        branch=branch,
        artifact_id=artifact_id,
        message=RENDER_TIMEOUT_MESSAGE,
        is_active=lambda candidate: _is_overdue(artifact=candidate, now=now),
    )
    if artifact is None:
        return None
    transformation_name = await _get_transformation_name(db=db, artifact=artifact)
    return RenderTimeout(artifact_id=artifact_id, branch=branch.name, transformation_name=transformation_name)


async def _get_transformation_name(db: InfrahubDatabase, artifact: CoreArtifact) -> str | None:
    """Return the name of the artifact's transformation, or None when its definition or transformation is gone."""
    try:
        definition = await artifact.definition.get_peer(db=db, peer_type=CoreArtifactDefinition, raise_on_error=True)
        transformation = await definition.transformation.get_peer(
            db=db, peer_type=CoreTransformation, raise_on_error=True
        )
    except (LookupError, NodeNotFoundError):
        return None
    return transformation.name.value


@flow(name="expire-artifact-renders", flow_run_name="Expire external artifact renders", persist_result=False)
async def expire_artifact_renders() -> None:
    """Set to Error the external renders whose engine did not answer before their deadline."""
    log = get_run_logger()
    database = await get_database()
    async with database.start_session() as db:
        timeouts = await expire_overdue_renders(db=db, event_service=await get_event_service(), now=Timestamp())
    for timeout in timeouts:
        log.warning(
            f"Artifact {timeout.artifact_id} on branch {timeout.branch} got no answer from the engine of "
            f"transformation {timeout.transformation_name} before its deadline"
        )

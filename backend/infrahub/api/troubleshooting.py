from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from infrahub import config
from infrahub.api.dependencies import BranchParams, get_branch_params, get_current_user, get_permission_manager
from infrahub.api.event_builder import make_event_meta
from infrahub.events import TraceSampleRatioUpdatedEvent
from infrahub.exceptions import ProcessingError
from infrahub.log import get_logger
from infrahub.message_bus.messages import RefreshSettingsTraceSampleRatio
from infrahub.permissions.globals import SUPER_ADMIN_PERMISSION
from infrahub.trace import (
    SampleRatioState,
    clear_temporary_sample_ratio,
    get_sample_ratio_state,
    set_temporary_sample_ratio,
)

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.permissions import PermissionManager
    from infrahub.services import InfrahubServices

router = APIRouter(prefix="/troubleshooting", tags=["troubleshooting"])
log = get_logger()

MAX_TEMPORARY_SAMPLE_RATIO_SECONDS = 86400
TRACE_SAMPLE_RATIO_PATH = "/trace-sample-ratio"


class TraceSampleRatioAPI(BaseModel):
    enabled: bool = Field(description="Indicates if tracing is enabled on this instance")
    default_ratio: float | None = Field(default=None, description="Ratio set by INFRAHUB_TRACE_SAMPLE_RATIO")
    temporary_ratio: float | None = Field(default=None, description="Ratio that replaces the default until expires_at")
    expires_at: datetime | None = Field(default=None, description="UTC time when the temporary ratio stops applying")
    ratio_in_force: float | None = Field(default=None, description="Share of new root traces recorded now")

    @classmethod
    def from_state(cls, state: SampleRatioState | None) -> TraceSampleRatioAPI:
        if state is None:
            return cls(enabled=False)
        return cls(
            enabled=True,
            default_ratio=state.default_ratio,
            temporary_ratio=state.temporary_ratio,
            expires_at=state.expires_at,
            ratio_in_force=state.ratio_in_force,
        )


class TraceSampleRatioUpdateAPI(BaseModel):
    ratio: float = Field(ge=0, le=1, allow_inf_nan=False, description="Share of new root traces to record")
    duration_seconds: int = Field(
        ge=1, le=MAX_TEMPORARY_SAMPLE_RATIO_SECONDS, description="Number of seconds the ratio applies"
    )


def _sample_ratio_state() -> SampleRatioState | None:
    if not config.SETTINGS.trace.enable:
        return None
    return get_sample_ratio_state()


def _require_sample_ratio_state() -> SampleRatioState:
    """Return the sampling state of this process.

    Raises:
        ProcessingError: When tracing is not enabled.

    """
    state = _sample_ratio_state()
    if state is None:
        raise ProcessingError("Tracing is not enabled on this instance; set INFRAHUB_TRACE_ENABLE")
    return state


async def _send_sample_ratio_updated_event(
    service: InfrahubServices,
    account_session: AccountSession,
    branch_params: BranchParams,
    previous: SampleRatioState,
    current: SampleRatioState,
    cleared: bool,
) -> None:
    try:
        event = TraceSampleRatioUpdatedEvent(
            meta=await make_event_meta(account_session=account_session, branch=branch_params.branch),
            previous_ratio=previous.ratio_in_force,
            new_ratio=current.ratio_in_force,
            expires_at=current.expires_at,
            cleared=cleared,
        )
        await service.event.send(event=event)
    # The event records a change every process already received; failing to send it must not fail the request
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Failed to emit the trace sample ratio event", account_id=account_session.account_id, error=str(exc)
        )


@router.get(
    TRACE_SAMPLE_RATIO_PATH,
    summary="Get the trace sampling ratio",
    description=(
        "Return the share of new traces that the API server process handling the request records: the default "
        "ratio set by INFRAHUB_TRACE_SAMPLE_RATIO, and the temporary ratio with its end time when one is in force. "
        "Use it during an incident to check the ratio before and after a change. Requires the super_admin "
        "permission."
    ),
)
async def get_trace_sample_ratio(
    permission_manager: PermissionManager = Depends(get_permission_manager),
) -> TraceSampleRatioAPI:
    permission_manager.raise_for_permission(permission=SUPER_ADMIN_PERMISSION)
    return TraceSampleRatioAPI.from_state(_sample_ratio_state())


@router.put(
    TRACE_SAMPLE_RATIO_PATH,
    summary="Set a temporary trace sampling ratio",
    description=(
        "Record a different share of new traces on every API server process and task worker until the duration "
        "ends, without a restart, because a restart can remove the slow behaviour under investigation. A new "
        'change replaces the active one. Each process applies the change within seconds and logs "Set the '
        'temporary trace sampling ratio". Requires the super_admin permission and INFRAHUB_TRACE_ENABLE.'
    ),
)
async def set_trace_sample_ratio(
    request: Request,
    update: TraceSampleRatioUpdateAPI,
    permission_manager: PermissionManager = Depends(get_permission_manager),
    account_session: AccountSession = Depends(get_current_user),
    branch_params: BranchParams = Depends(get_branch_params),
) -> TraceSampleRatioAPI:
    permission_manager.raise_for_permission(permission=SUPER_ADMIN_PERMISSION)
    previous = _require_sample_ratio_state()

    expires_at = datetime.now(tz=UTC) + timedelta(seconds=update.duration_seconds)
    # The broadcast reaches this process too, but later; applying it here first makes the response show the change.
    set_temporary_sample_ratio(ratio=update.ratio, expires_at=expires_at)
    current = _require_sample_ratio_state()

    service: InfrahubServices = request.app.state.service
    await service.send(message=RefreshSettingsTraceSampleRatio(ratio=update.ratio, expires_at=expires_at))
    await _send_sample_ratio_updated_event(
        service=service,
        account_session=account_session,
        branch_params=branch_params,
        previous=previous,
        current=current,
        cleared=False,
    )
    return TraceSampleRatioAPI.from_state(current)


@router.delete(
    TRACE_SAMPLE_RATIO_PATH,
    summary="Clear the temporary trace sampling ratio",
    description=(
        "Go back to the default trace sampling ratio on every API server process and task worker. Each process "
        'applies the change within seconds and logs "Cleared the temporary trace sampling ratio". Requires the '
        "super_admin permission and INFRAHUB_TRACE_ENABLE."
    ),
)
async def clear_trace_sample_ratio(
    request: Request,
    permission_manager: PermissionManager = Depends(get_permission_manager),
    account_session: AccountSession = Depends(get_current_user),
    branch_params: BranchParams = Depends(get_branch_params),
) -> TraceSampleRatioAPI:
    permission_manager.raise_for_permission(permission=SUPER_ADMIN_PERMISSION)
    previous = _require_sample_ratio_state()

    clear_temporary_sample_ratio()
    current = _require_sample_ratio_state()

    service: InfrahubServices = request.app.state.service
    await service.send(message=RefreshSettingsTraceSampleRatio(ratio=None, expires_at=None))
    await _send_sample_ratio_updated_event(
        service=service,
        account_session=account_session,
        branch_params=branch_params,
        previous=previous,
        current=current,
        cleared=True,
    )
    return TraceSampleRatioAPI.from_state(current)

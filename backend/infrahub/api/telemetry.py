from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from infrahub.api.dependencies import get_current_user, get_db, get_permission_manager
from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.telemetry.snapshot import TelemetrySnapshot

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions.manager import PermissionManager

router = APIRouter(prefix="/telemetry")


class TelemetrySnapshotResponse(BaseModel):
    id: str
    created_at: str
    kind: str
    payload_format: str
    deployment_id: str
    infrahub_version: str
    data: dict[str, Any]
    checksum: str
    remote_send_status: str


class TelemetrySnapshotListResponse(BaseModel):
    count: int
    snapshots: list[TelemetrySnapshotResponse]


def _snapshot_to_response(snapshot: TelemetrySnapshot) -> TelemetrySnapshotResponse:
    return TelemetrySnapshotResponse(
        id=str(snapshot.uuid),
        created_at=snapshot.created_at or "",
        kind=snapshot.kind,
        payload_format=snapshot.payload_format,
        deployment_id=snapshot.deployment_id,
        infrahub_version=snapshot.infrahub_version,
        data=snapshot.data,
        checksum=snapshot.checksum,
        remote_send_status=snapshot.remote_send_status,
    )


@router.get("/snapshots")
async def get_telemetry_snapshots(
    db: InfrahubDatabase = Depends(get_db),
    _: AccountSession = Depends(get_current_user),
    permission_manager: PermissionManager = Depends(get_permission_manager),
    start_date: str | None = Query(
        default=None, description="Include snapshots created on or after this date (ISO 8601)"
    ),
    end_date: str | None = Query(
        default=None, description="Include snapshots created on or before this date (ISO 8601)"
    ),
    limit: int = Query(default=1000, ge=1, description="Maximum number of snapshots to return"),
    offset: int = Query(default=0, ge=0, description="Number of snapshots to skip"),
) -> TelemetrySnapshotListResponse:
    permission_manager.raise_for_permission(
        permission=GlobalPermission(
            action=GlobalPermissions.READ_TELEMETRY.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
    )

    snapshots = await TelemetrySnapshot.get_list_filtered(
        db=db,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return TelemetrySnapshotListResponse(
        count=len(snapshots),
        snapshots=[_snapshot_to_response(s) for s in snapshots],
    )

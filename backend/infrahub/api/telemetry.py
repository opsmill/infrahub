"""REST API endpoints for telemetry data export and management.

These endpoints support airgapped environments by allowing manual export
of locally stored telemetry data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from infrahub import config
from infrahub.api.dependencies import get_current_user
from infrahub.license.loader import get_current_license
from infrahub.telemetry.storage import (
    get_local_telemetry_status,
    list_local_telemetry,
    load_telemetry_file,
)

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.auth import AccountSession

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryFileInfo(BaseModel):
    """Information about a local telemetry file."""

    date: str
    filename: str
    size: str


class TelemetryListResponse(BaseModel):
    """Response for listing local telemetry files."""

    files: list[TelemetryFileInfo] = Field(default_factory=list)


class LicenseInfo(BaseModel):
    """License information for telemetry responses."""

    license_id: str | None = None
    customer_name: str | None = None
    deployment_id: str | None = None
    product_tier: str | None = None
    support_tier: str | None = None
    valid: bool = False


class TelemetryStatusResponse(BaseModel):
    """Response for telemetry status endpoint."""

    enabled: bool
    storage_path: str
    retention_days: int
    files_count: int
    latest_file: str | None = None
    license: LicenseInfo | None = None


class TelemetrySnapshot(BaseModel):
    """A single telemetry snapshot in export format."""

    date: str
    data: dict[str, Any]


class TelemetryExportResponse(BaseModel):
    """Response for telemetry export endpoint."""

    export_version: str = "1.0"
    exported_at: str
    license: LicenseInfo | None = None
    snapshots: list[TelemetrySnapshot] = Field(default_factory=list)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    size_float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size_float < 1024:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024
    return f"{size_float:.1f} TB"


def _get_license_info() -> LicenseInfo | None:
    """Get license information for API responses."""
    license_status = get_current_license()
    if not license_status.valid or not license_status.license_data:
        return LicenseInfo(valid=False)

    data = license_status.license_data
    return LicenseInfo(
        license_id=str(data.license_id),
        customer_name=data.customer_name,
        deployment_id=str(data.deployment_id),
        product_tier=data.product_tier.value,
        support_tier=data.support_tier.value,
        valid=True,
    )


def _extract_date_from_filename(filepath: Path) -> str:
    """Extract date from telemetry filename."""
    # Format: telemetry-{deployment_id}-{date}.json
    name = filepath.stem
    parts = name.split("-")
    if len(parts) >= 3:
        return parts[-1]
    return "unknown"


def _date_str_to_datetime(date_str: str) -> datetime:
    """Convert a date string (YYYY-MM-DD) to a datetime object."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)


@router.get("/status")
async def get_telemetry_status(
    _: AccountSession = Depends(get_current_user),
) -> TelemetryStatusResponse:
    """Get telemetry configuration and status.

    Returns the current telemetry configuration including whether telemetry
    is enabled, the storage path, and retention settings.
    """
    status = await get_local_telemetry_status()

    return TelemetryStatusResponse(
        enabled=not config.SETTINGS.main.telemetry_optout,
        storage_path=status["storage_path"],
        retention_days=status["retention_days"],
        files_count=status["files_count"],
        latest_file=status.get("latest_file"),
        license=_get_license_info(),
    )


@router.get("/list")
async def list_telemetry_files(
    _: AccountSession = Depends(get_current_user),
) -> TelemetryListResponse:
    """List available local telemetry files.

    Shows all telemetry files stored locally on the Infrahub instance,
    including their dates and sizes.
    """
    files = await list_local_telemetry()

    file_infos = []
    for filepath in files:
        stat = filepath.stat()
        file_infos.append(
            TelemetryFileInfo(
                date=_extract_date_from_filename(filepath),
                filename=filepath.name,
                size=_format_file_size(stat.st_size),
            )
        )

    # Sort by date descending
    file_infos.sort(key=lambda f: f.date, reverse=True)

    return TelemetryListResponse(files=file_infos)


@router.get("/export")
async def export_telemetry(
    _: AccountSession = Depends(get_current_user),
    from_date: str | None = Query(None, description="Start date for export range (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="End date for export range (YYYY-MM-DD)"),
    export_all: bool = Query(False, alias="all", description="Export all available telemetry data"),
) -> TelemetryExportResponse:
    """Export telemetry data for airgapped transfer.

    This endpoint exports locally stored telemetry data into a format
    suitable for manual transfer to OpsMill for airgapped environments.

    Args:
        from_date: Optional start date for export range (YYYY-MM-DD)
        to_date: Optional end date for export range (YYYY-MM-DD)
        export_all: If true, export all available data regardless of date range
    """
    # Convert date strings to datetime objects
    from_datetime: datetime | None = None
    to_datetime: datetime | None = None

    # If export_all is set, ignore date filters
    if not export_all:
        if from_date:
            from_datetime = _date_str_to_datetime(from_date)
        if to_date:
            to_datetime = _date_str_to_datetime(to_date)

    files = await list_local_telemetry(from_date=from_datetime, to_date=to_datetime)

    snapshots = []
    for filepath in files:
        data = await load_telemetry_file(filepath)
        if data:
            snapshots.append(
                TelemetrySnapshot(
                    date=_extract_date_from_filename(filepath),
                    data=data,
                )
            )

    # Sort by date ascending for export
    snapshots.sort(key=lambda s: s.date)

    return TelemetryExportResponse(
        export_version="1.0",
        exported_at=datetime.now(tz=UTC).isoformat(),
        license=_get_license_info(),
        snapshots=snapshots,
    )

"""Local telemetry storage for airgapped environments and audit trails.

This module provides functionality to save telemetry data locally before
streaming to the telemetry endpoint. This enables:
- Backfill/export for airgapped environments
- Audit trail even if streaming fails
- Customers to review what data is being sent
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from infrahub import config

logger = logging.getLogger(__name__)


def _get_storage_path() -> Path:
    """Get the configured telemetry storage path."""
    return Path(config.SETTINGS.main.telemetry_storage_path)


def _get_retention_days() -> int:
    """Get the configured retention days."""
    return config.SETTINGS.main.telemetry_storage_retention_days


async def save_telemetry_locally(data: dict[str, Any], deployment_id: str) -> Path:
    """Save telemetry payload to local storage.

    Args:
        data: The telemetry payload.
        deployment_id: Unique deployment identifier.

    Returns:
        Path to the saved file.
    """
    storage_path = _get_storage_path()
    storage_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    filename = f"telemetry-{deployment_id}-{today}.json"
    filepath = storage_path / filename

    content = json.dumps(data, indent=2, default=str)
    filepath.write_text(content, encoding="utf-8")

    logger.info(f"Telemetry saved locally: {filepath}")
    return filepath


async def cleanup_old_telemetry() -> int:
    """Remove telemetry files older than retention period.

    Returns:
        Number of files removed.
    """
    storage_path = _get_storage_path()
    if not storage_path.exists():
        return 0

    retention_days = _get_retention_days()
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
    removed = 0

    for filepath in storage_path.glob("telemetry-*.json"):
        try:
            if filepath.stat().st_mtime < cutoff.timestamp():
                filepath.unlink()
                removed += 1
                logger.debug(f"Removed old telemetry file: {filepath}")
        except OSError as e:
            logger.warning(f"Failed to remove old telemetry file {filepath}: {e}")

    if removed:
        logger.info(f"Cleaned up {removed} old telemetry file(s)")

    return removed


def _extract_date_from_filename(filename: str) -> str | None:
    """Extract the date portion from a telemetry filename.

    Args:
        filename: The filename to extract date from.

    Returns:
        Date string (YYYY-MM-DD) if found, None otherwise.
    """
    # Pattern: telemetry-{deployment_id}-{date}.json
    match = re.search(r"telemetry-[a-f0-9-]+-(\d{4}-\d{2}-\d{2})\.json$", filename)
    if match:
        return match.group(1)
    return None


async def list_local_telemetry(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> list[Path]:
    """List available local telemetry files.

    Args:
        from_date: Start of date range (inclusive).
        to_date: End of date range (inclusive).

    Returns:
        List of file paths sorted by date.
    """
    storage_path = _get_storage_path()
    if not storage_path.exists():
        return []

    files: list[Path] = []
    for filepath in sorted(storage_path.glob("telemetry-*.json")):
        # Extract date from filename for filtering
        date_str = _extract_date_from_filename(filepath.name)
        if date_str:
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)

                # Apply date filters
                if from_date and file_date < from_date:
                    continue
                if to_date and file_date > to_date:
                    continue

                files.append(filepath)
            except ValueError:
                # If date parsing fails, include the file anyway
                files.append(filepath)
        else:
            files.append(filepath)

    return files


async def get_local_telemetry_status() -> dict[str, Any]:
    """Get status information about local telemetry storage.

    Returns:
        Dictionary with storage status information.
    """
    storage_path = _get_storage_path()
    files = await list_local_telemetry()

    status: dict[str, Any] = {
        "enabled": not config.SETTINGS.main.telemetry_optout,
        "storage_path": str(storage_path),
        "retention_days": _get_retention_days(),
        "files_count": len(files),
        "latest_file": None,
    }

    if files:
        latest = files[-1]
        status["latest_file"] = latest.name

    return status


async def load_telemetry_file(filepath: Path) -> dict[str, Any] | None:
    """Load a telemetry file from disk.

    Args:
        filepath: Path to the telemetry file.

    Returns:
        Parsed JSON data or None if loading fails.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
        return json.loads(content)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load telemetry file {filepath}: {e}")
        return None

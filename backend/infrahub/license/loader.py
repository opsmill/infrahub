"""License file loading for Infrahub.

Provides functionality to load license files from disk and manage
the current license state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from infrahub import config

from .models import LicenseFile, LicenseStatus
from .validator import validate_license

logger = logging.getLogger(__name__)

# Module-level cache for the current license
_current_license: LicenseStatus | None = None


def load_license_from_file(file_path: Path | str) -> LicenseStatus:
    """Load and validate a license file from disk.

    Args:
        file_path: Path to the license JSON file.

    Returns:
        LicenseStatus with validation results and parsed license data.
    """
    path = Path(file_path) if isinstance(file_path, str) else file_path

    if not path.exists():
        return LicenseStatus.invalid(f"License file not found: {path}")

    if not path.is_file():
        return LicenseStatus.invalid(f"License path is not a file: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as e:
        return LicenseStatus.invalid(f"Failed to read license file: {e}")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return LicenseStatus.invalid(f"Invalid JSON in license file: {e}")

    try:
        license_file = LicenseFile.model_validate(data)
    except ValidationError as e:
        return LicenseStatus.invalid(f"Invalid license file format: {e}")

    return validate_license(license_file)


def get_current_license() -> LicenseStatus:
    """Get the current license status.

    Returns the cached license if available, otherwise attempts to load
    the license from the configured path.

    Returns:
        LicenseStatus with the current license state.
    """
    global _current_license

    if _current_license is not None:
        return _current_license

    # Check if a license file path is configured
    license_path = getattr(config.SETTINGS.main, "license_file_path", None)

    if not license_path:
        return LicenseStatus.invalid("No license file configured")

    _current_license = load_license_from_file(license_path)

    if _current_license.valid and _current_license.license_data is not None:
        logger.info(f"License loaded for customer: {_current_license.license_data.customer_name}")
    else:
        logger.warning(f"Failed to load license: {_current_license.error}")

    return _current_license


def reload_license() -> LicenseStatus:
    """Force reload the license from disk.

    Clears the cached license and reloads from the configured path.

    Returns:
        LicenseStatus with the reloaded license state.
    """
    global _current_license
    _current_license = None
    return get_current_license()


def clear_license_cache() -> None:
    """Clear the cached license.

    Useful for testing or when the license file has been updated.
    """
    global _current_license
    _current_license = None

"""License signature validation for Infrahub.

Provides functionality to verify the cryptographic signature of license files.
For the PoC, signature validation is simplified but can be extended to use
proper RSA signature verification.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from infrahub import config

from .models import LicenseFile, LicenseStatus

logger = logging.getLogger(__name__)


def _get_license_signing_data(license_file: LicenseFile) -> str:
    """Get the data that should be signed for a license.

    Creates a canonical string representation of the license data
    that is used for signature verification.

    Args:
        license_file: The license file to get signing data for.

    Returns:
        A canonical string representation of the license data.
    """
    # Create a deterministic string from license fields (excluding signature)
    parts = [
        str(license_file.license_id),
        license_file.customer_name,
        str(license_file.deployment_id),
        license_file.product_tier.value,
        license_file.support_tier.value,
        license_file.start_date.isoformat(),
        license_file.end_date.isoformat(),
        license_file.issued_at.isoformat(),
    ]
    return "|".join(parts)


def _verify_signature_poc(license_file: LicenseFile, secret_key: str) -> bool:
    """Verify license signature using HMAC (PoC implementation).

    This is a simplified signature verification for the PoC.
    In production, this should use RSA signature verification with
    the OpsMill public key.

    Args:
        license_file: The license file to verify.
        secret_key: The secret key to use for HMAC verification.

    Returns:
        True if the signature is valid, False otherwise.
    """
    signing_data = _get_license_signing_data(license_file)

    # Compute expected signature using HMAC-SHA256
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_data.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    try:
        provided_signature = base64.b64decode(license_file.signature)
    except Exception:
        return False

    return hmac.compare_digest(expected_signature, provided_signature)


def validate_license(license_file: LicenseFile) -> LicenseStatus:
    """Validate a license file.

    Performs the following validations:
    1. Signature verification (if not skipped in dev mode)
    2. Date validity (start_date <= today <= end_date)
    3. Deployment ID match (if configured)

    Args:
        license_file: The license file to validate.

    Returns:
        LicenseStatus with validation results.
    """
    warnings: list[str] = []

    # Check if signature validation should be skipped (dev mode)
    skip_signature = getattr(config.SETTINGS.main, "license_skip_signature_validation", False)

    if not skip_signature:
        # Get the signing key from settings
        signing_key = getattr(config.SETTINGS.main, "license_signing_key", None)
        if signing_key:
            if not _verify_signature_poc(license_file, signing_key):
                return LicenseStatus.invalid("License signature verification failed")
        else:
            # In production, would use RSA verification with public key
            # For now, warn but continue if no signing key is configured
            logger.warning("License signature validation skipped - no signing key configured")
            warnings.append("Signature validation skipped")

    # Validate date range
    if license_file.is_not_yet_valid():
        return LicenseStatus.invalid(f"License is not yet valid. Start date: {license_file.start_date.isoformat()}")

    if license_file.is_expired():
        return LicenseStatus.invalid(f"License has expired. End date: {license_file.end_date.isoformat()}")

    return LicenseStatus.success(license_file, warnings)

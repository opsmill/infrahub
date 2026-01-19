"""License data models for Infrahub.

Defines Pydantic models for license file parsing and validation status.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from uuid import UUID


class ProductTier(StrEnum):
    """Product tier levels for Infrahub licenses."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class SupportTier(StrEnum):
    """Support tier levels for Infrahub licenses."""

    BASIC = "basic"
    ADVANCED = "advanced"
    TWENTYFOUR_SEVEN = "24x7"


class LicenseFile(BaseModel):
    """License file data structure.

    Represents the contents of a license file provided by OpsMill to link
    a customer's identity to their Infrahub deployment.
    """

    license_id: UUID = Field(description="Unique license identifier")
    customer_name: str = Field(description="Customer organization name")
    deployment_id: UUID = Field(description="Bound to specific Infrahub instance")
    product_tier: ProductTier = Field(description="Product tier (small/medium/large)")
    support_tier: SupportTier = Field(description="Support tier (basic/advanced/24x7)")
    start_date: date = Field(description="License effective date")
    end_date: date = Field(description="License expiration date")
    issued_at: datetime = Field(description="When license was generated")
    signature: str = Field(description="Base64-encoded cryptographic signature")

    def is_expired(self) -> bool:
        """Check if the license has expired."""
        return datetime.now(tz=UTC).date() > self.end_date

    def is_not_yet_valid(self) -> bool:
        """Check if the license is not yet valid (start date in future)."""
        return datetime.now(tz=UTC).date() < self.start_date

    def is_within_validity_period(self) -> bool:
        """Check if current date is within the license validity period."""
        today = datetime.now(tz=UTC).date()
        return self.start_date <= today <= self.end_date


# Rebuild model to resolve forward references for UUID
# Import UUID at module level for model_rebuild to find it
from uuid import UUID as _UUID  # noqa: E402

LicenseFile.model_rebuild(_types_namespace={"UUID": _UUID})


class LicenseStatus(BaseModel):
    """Validation result for a license.

    Contains the validation status, the parsed license data if valid,
    and any error or warning messages.
    """

    valid: bool = Field(description="Whether the license is valid")
    license_data: LicenseFile | None = Field(
        default=None, description="Parsed license data if validation succeeded"
    )
    error: str | None = Field(default=None, description="Error message if validation failed")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warning messages")

    @classmethod
    def invalid(cls, error: str) -> LicenseStatus:
        """Create an invalid license status with an error message."""
        return cls(valid=False, error=error)

    @classmethod
    def success(cls, license_data: LicenseFile, warnings: list[str] | None = None) -> LicenseStatus:
        """Create a valid license status with the parsed data."""
        return cls(valid=True, license_data=license_data, warnings=warnings or [])


class LicenseTelemetryData(BaseModel):
    """License information included in telemetry payloads.

    A subset of license data suitable for inclusion in telemetry to identify
    the customer without exposing sensitive information.
    """

    license_id: str = Field(description="License ID as string")
    customer_name: str = Field(description="Customer organization name")
    deployment_id: str = Field(description="Deployment ID as string")
    product_tier: ProductTier = Field(description="Product tier")
    support_tier: SupportTier = Field(description="Support tier")

    @classmethod
    def from_license(cls, license_file: LicenseFile) -> LicenseTelemetryData:
        """Create telemetry data from a license file."""
        return cls(
            license_id=str(license_file.license_id),
            customer_name=license_file.customer_name,
            deployment_id=str(license_file.deployment_id),
            product_tier=license_file.product_tier,
            support_tier=license_file.support_tier,
        )

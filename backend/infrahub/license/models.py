from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class LicenseState(StrEnum):
    """The single license state derived for a moment in time; also exposed to API clients and telemetry."""

    NOT_REQUIRED = "not_required"
    UNLICENSED = "unlicensed"
    INVALID = "invalid"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    EXPIRING = "expiring"
    VALID = "valid"


class LicenseFailureReason(StrEnum):
    """Why a supplied license could not be verified; also exposed to API clients."""

    MALFORMED = "malformed"
    BAD_SIGNATURE = "bad_signature"
    UNKNOWN_KEY = "unknown_key"
    WRONG_ISSUER = "wrong_issuer"
    WRONG_PRODUCT = "wrong_product"
    INTERNAL_ERROR = "internal_error"


class LicenseType(StrEnum):
    EVALUATION = "evaluation"
    COMMERCIAL = "commercial"


class NoticeMode(StrEnum):
    """Release-wide rule for license notices: super-admins only and no header, or enforced for every user."""

    QUIET = "quiet"
    ENFORCE = "enforce"


class NoticeAudience(StrEnum):
    NONE = "none"
    SUPER_ADMINS = "super_admins"
    ALL_USERS = "all_users"


def _as_utc(field_name: str, value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(f"License '{field_name}' must be timezone-aware, got {value.isoformat()}")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class License:
    """Verified content of a license; raises ValueError on a naive datetime or an end not after the start."""

    license_id: str
    customer_name: str
    license_type: str
    """Kept as received; a value that is not a known license type is treated as commercial."""

    product_tier: str
    support_tier: str
    starts_at: datetime
    ends_at: datetime
    """First instant the license is no longer valid."""

    issued_at: datetime
    issuer: str

    def __post_init__(self) -> None:
        # The dataclass is frozen, so normalizing a field has to bypass its own __setattr__.
        object.__setattr__(self, "starts_at", _as_utc(field_name="starts_at", value=self.starts_at))
        object.__setattr__(self, "ends_at", _as_utc(field_name="ends_at", value=self.ends_at))
        object.__setattr__(self, "issued_at", _as_utc(field_name="issued_at", value=self.issued_at))
        if self.ends_at <= self.starts_at:
            raise ValueError(
                f"License 'ends_at' must be later than 'starts_at', got starts_at={self.starts_at.isoformat()} "
                f"ends_at={self.ends_at.isoformat()}"
            )

    @property
    def is_evaluation(self) -> bool:
        return self.license_type == LicenseType.EVALUATION


@dataclass(frozen=True)
class LicenseFailure:
    reason: LicenseFailureReason


@dataclass(frozen=True)
class LicenseStatus:
    state: LicenseState
    reason: LicenseFailureReason | None = None
    """Set only when the state is invalid."""

    license: License | None = None
    """Set whenever verification produced a license, including when it is not yet valid or expired."""

    days_remaining: int | None = None
    """Whole days until the license ends, rounded up; None once it has ended."""

    days_since_expiry: int | None = None
    """Whole days since the license ended, rounded down; None until it ends."""


@dataclass(frozen=True)
class Notice:
    audience: NoticeAudience
    dismissible: bool
    send_header: bool
    """Whether API responses carry the license status header."""

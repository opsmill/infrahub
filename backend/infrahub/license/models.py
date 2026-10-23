from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
from typing import assert_never


class LicenseState(StrEnum):
    """The single license state derived for a moment in time."""

    NOT_REQUIRED = "not_required"
    UNLICENSED = "unlicensed"
    INVALID = "invalid"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    EXPIRING = "expiring"
    VALID = "valid"


class LicenseFailureReason(StrEnum):
    """Why a supplied license could not be verified."""

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
    """Release-wide notice rule: super-admins only and no header, or license problems shown to every user."""

    QUIET = "quiet"
    ENFORCE = "enforce"


class NoticeAudience(StrEnum):
    NONE = "none"
    SUPER_ADMINS = "super_admins"
    ALL_USERS = "all_users"


_TEXT_FIELDS = ("license_id", "customer_name", "license_type", "product_tier", "support_tier", "issuer")


def _as_utc(field_name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"License '{field_name}' must be a datetime, got {type(value).__name__}")
    if value.utcoffset() is None:
        raise ValueError(f"License '{field_name}' must be timezone-aware, got {value.isoformat()}")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class License:
    """Verified license content; raises ValueError on a wrong field type, a naive datetime or ends_at <= starts_at."""

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
        for field_name in _TEXT_FIELDS:
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"License '{field_name}' must be a string, got {type(value).__name__}")
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


def _details_set_in(state: LicenseState) -> list[str]:
    match state:
        case LicenseState.NOT_REQUIRED | LicenseState.UNLICENSED:
            return []
        case LicenseState.INVALID:
            return ["reason"]
        case LicenseState.NOT_YET_VALID | LicenseState.VALID | LicenseState.EXPIRING:
            return ["days_remaining", "license"]
        case LicenseState.EXPIRED:
            return ["days_since_expiry", "license"]
        case _:
            assert_never(state)


@dataclass(frozen=True)
class LicenseStatus:
    """A license state and the details that state carries; raises ValueError on a missing or an extra detail."""

    state: LicenseState
    reason: LicenseFailureReason | None = None
    """Set only when the state is invalid."""

    license: License | None = None
    """Set only when verification produced a license: not yet valid, valid, expiring or expired."""

    days_remaining: int | None = None
    """Whole days until the license ends, rounded up; set only before it ends."""

    days_since_expiry: int | None = None
    """Whole days since the license ended, rounded down; set only once it has ended."""

    def __post_init__(self) -> None:
        details_set = sorted(
            field.name for field in fields(self) if field.name != "state" and getattr(self, field.name) is not None
        )
        details_required = _details_set_in(self.state)
        if details_set != details_required:
            raise ValueError(f"License status '{self.state}' must set exactly {details_required}, got {details_set}")


@dataclass(frozen=True)
class Notice:
    audience: NoticeAudience
    dismissible: bool
    send_header: bool
    """Whether API responses carry the license status header."""

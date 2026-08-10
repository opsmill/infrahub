from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from infrahub.exceptions import ValidationError


def normalize_timezone(value: str | None) -> str | None:
    """Return a stored-ready timezone, rejecting anything the runtime cannot resolve.

    An empty value is normalized to None (nothing stored) so the write reply agrees with every
    later read, which treats a falsy timezone as unset. A non-empty value must resolve against the
    runtime's zone database; validating by construction accepts every zone that has a data file
    (backward-compatibility aliases included), rather than an enumerated allowlist that would reject
    aliases a client legitimately offers.

    Raises:
        ValidationError: the value is non-empty but names no timezone the runtime can resolve.

    """
    if not value:
        return None
    try:
        # OSError covers keys the resolver rejects at the filesystem layer (e.g. an over-long name);
        # ValueError covers malformed keys; ZoneInfoNotFoundError covers well-formed-but-absent ones.
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ValidationError(input_value=f"'{value}' is not a valid IANA timezone") from exc
    return value

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from infrahub.exceptions import ValidationError

# Implementation-defined entries a full zone tree resolves but browsers reject; listed explicitly
# so they are refused regardless of which zone tree the runtime ships.
_REJECTED_KEYS = frozenset({"localtime", "posixrules"})
_REJECTED_PREFIXES = ("posix/", "right/")


def normalize_timezone(value: str | None) -> str | None:
    """Return a stored-ready timezone, rejecting anything a client should not store.

    An empty value is normalized to None (nothing stored) so the write reply agrees with every
    later read, which treats a falsy timezone as unset. A non-empty value must resolve against the
    runtime's zone database and not be an implementation-defined entry; validating by construction
    (rather than an enumerated allowlist) keeps the check independent of an enumeration that varies
    by runtime and avoids a filesystem walk.

    Raises:
        ValidationError: the value is non-empty but is not a storable IANA timezone.

    """
    if not value:
        return None
    if value in _REJECTED_KEYS or value.startswith(_REJECTED_PREFIXES):
        raise ValidationError(input_value=f"'{value}' is not a valid IANA timezone")
    try:
        # OSError covers keys the resolver rejects at the filesystem layer (e.g. an over-long name);
        # ValueError covers malformed keys; ZoneInfoNotFoundError covers well-formed-but-absent ones.
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ValidationError(input_value=f"'{value}' is not a valid IANA timezone") from exc
    return value

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from infrahub.core.preferences.constants import INSTANCE_LABEL_MAX_LENGTH
from infrahub.exceptions import ValidationError

# Implementation-defined entries a full zone tree resolves but browsers reject; listed explicitly
# so they are refused regardless of which zone tree the runtime ships.
_REJECTED_KEYS = frozenset({"localtime", "posixrules"})
_REJECTED_PREFIXES = ("posix/", "right/")


def validate_timezone(value: str | None) -> str | None:
    """Validate a timezone for storage; empty becomes None, a valid value is returned unchanged.

    A non-empty value must resolve against the runtime's zone database and not be an
    implementation-defined key. It is checked by construction rather than an allowlist, so
    backward-compatibility aliases are accepted and stored as given. The accepted set follows the
    interpreter's own tzdata, so confirm new accept/reject behavior against a running instance,
    not by unit test alone.

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


def validate_instance_label(value: str | None) -> str | None:
    """Validate an instance label for storage; it is stripped, and an empty result becomes None.

    Raises:
        ValidationError: the stripped value contains a line break or exceeds the length limit.

    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if "\n" in stripped or "\r" in stripped:
        raise ValidationError(input_value="instance_label cannot contain a line break")
    if len(stripped) > INSTANCE_LABEL_MAX_LENGTH:
        raise ValidationError(
            input_value=f"instance_label cannot be longer than {INSTANCE_LABEL_MAX_LENGTH} characters"
        )
    return stripped

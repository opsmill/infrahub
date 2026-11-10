from __future__ import annotations

import unicodedata

from infrahub.exceptions import ValidationError
from infrahub.utils import InfrahubStringEnum


class InstanceColor(InfrahubStringEnum):
    """Preset colors an administrator can assign to the instance; clients map each to their own theme."""

    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"
    BLUE = "BLUE"
    INDIGO = "INDIGO"
    PURPLE = "PURPLE"
    GRAY = "GRAY"


# Upper bound on the trimmed instance label, so it fits in the header and leaves room for the page
# title in a browser tab.
INSTANCE_LABEL_MAX_LENGTH = 32

# Bidirectional controls and direction marks are category Cf, not Cc, so they need listing: a
# label carrying one is rendered with its characters reordered.
_BIDI_CONTROL_CHARACTERS = frozenset(map(chr, (0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A))))


def _contains_control_character(value: str) -> bool:
    return any(unicodedata.category(char) == "Cc" or char in _BIDI_CONTROL_CHARACTERS for char in value)


def validate_instance_label(value: str | None, field_name: str = "instance_label") -> str | None:
    """Validate an instance label for storage; it is stripped, and an empty result becomes None.

    Raises:
        ValidationError: the stripped value contains a control character or exceeds the length limit.

    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if _contains_control_character(stripped):
        raise ValidationError(input_value=f"{field_name} cannot contain control characters")
    if len(stripped) > INSTANCE_LABEL_MAX_LENGTH:
        raise ValidationError(input_value=f"{field_name} cannot be longer than {INSTANCE_LABEL_MAX_LENGTH} characters")
    return stripped

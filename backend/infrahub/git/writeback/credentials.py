from __future__ import annotations

import re

# The match starts where a run of scheme characters starts, so a URL right after a digit or an "_" is found.
# The rest stops only at characters that a URL never holds raw, as a "'" can be part of a password.
URL = re.compile(r"(?P<scheme>(?<![A-Za-z0-9+.-])[0-9+.-]*[A-Za-z][A-Za-z0-9+.-]*://)(?P<rest>[^\s\"<>]*)")


def scrub_credentials(*, text: str) -> str:
    """Remove the user name and the password from every URL in the text."""
    return URL.sub(_without_user_part, text)


def _without_user_part(match: re.Match[str]) -> str:
    # A password can hold "@", "/", "?" or "#", so everything up to the last "@" of the URL goes.
    _, at_sign, after = match.group("rest").rpartition("@")
    return match.group("scheme") + (after if at_sign else match.group("rest"))

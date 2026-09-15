from __future__ import annotations

from typing import Any

from infrahub_sdk.schema import format_error_location


def error_paths(detail: list[dict[str, Any]]) -> list[tuple[str, Any, str]]:
    """Flatten a 422 ``detail`` list into ``(path, input, msg)`` rows.

    The location list is rendered as a dotted field path (``body.schemas[0].nodes[0].name``) so an
    assertion reads as the address of the offending field rather than as a list of segments.
    """
    return [(format_error_location(loc=item["loc"]), item["input"], item["msg"]) for item in detail]

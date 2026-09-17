from __future__ import annotations

from typing import Any


def dotted_path(loc: list[int | str]) -> str:
    """Render a pydantic-style location as a dotted field path.

    Integer elements index into the preceding segment (``attributes`` + ``1`` becomes
    ``attributes[1]``); everything else is appended as a new dotted segment.
    """
    parts: list[str] = []
    for element in loc:
        if isinstance(element, int):
            parts[-1] = f"{parts[-1]}[{element}]" if parts else f"[{element}]"
        else:
            parts.append(str(element))
    return ".".join(parts)


def error_paths(detail: list[dict[str, Any]]) -> list[tuple[str, Any, str]]:
    """Flatten a 422 ``detail`` list into ``(path, input, msg)`` rows.

    The location list is rendered as a dotted field path (``body.schemas[0].nodes[0].name``) so an
    assertion reads as the address of the offending field rather than as a list of segments.
    """
    return [(dotted_path(loc=item["loc"]), item["input"], item["msg"]) for item in detail]

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


def build_peer_filters(*, field_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Return the filters a read of ``field_name`` applies to its peers, keyed for the peer query.

    Values that are false, zero or empty are ignored, except for ``id`` and ``ids``, and so are arguments that are
    not filters, such as pagination.
    """
    return {
        f"{field_name}__{key}": value
        for key, value in arguments.items()
        if ("__" in key and value) or key in {"id", "ids"}
    }

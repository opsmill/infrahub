from __future__ import annotations

from typing import Union


def element_id_to_id(element_id: Union[str, int]) -> int:
    if isinstance(element_id, int):
        return element_id

    if isinstance(element_id, str) and ":" not in element_id:
        return int(element_id)

    return int(element_id.split(":")[2])


def extract_field_filters(field_name: str, filters: dict) -> dict:
    """Extract the filters for a given field (attribute or relationship) from a filters dict."""
    return {
        key.replace(f"{field_name}__", ""): value for key, value in filters.items() if key.startswith(f"{field_name}__")
    }

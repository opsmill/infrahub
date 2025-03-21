from typing import Any


def to_frozen_set(to_freeze: dict[str, Any]) -> frozenset:
    freezing_dict = {}
    for k, v in to_freeze.items():
        if isinstance(v, dict):
            freezing_dict[k] = to_frozen_set(v)
        elif isinstance(v, list | set):
            freezing_dict[k] = frozenset(v)
        else:
            freezing_dict[k] = v
    return frozenset(freezing_dict)

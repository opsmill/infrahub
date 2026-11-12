from __future__ import annotations

from infrahub.core.node.lock_utils import build_object_lock_name
from infrahub.rack_elevation.constants import RACK_ELEVATION_LOCK_NAMESPACE


def rack_lock_name(branch_name: str, rack_id: str) -> str:
    return build_object_lock_name(f"{RACK_ELEVATION_LOCK_NAMESPACE}.{branch_name}.{rack_id}")

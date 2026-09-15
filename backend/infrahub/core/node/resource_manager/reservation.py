from __future__ import annotations

import ipaddress
from typing import Any

from infrahub.exceptions import ValidationError


def validate_reserved_prefix_length(
    *,
    pool_kind: str,
    pool_name: str,
    reserved_value: Any,
    prefixlen: int | None,
    data: dict[str, Any] | None,
) -> None:
    """Guard re-allocation of an existing pool reservation against a conflicting prefix length.

    Pool allocation is idempotent on the reservation identifier: once a resource is reserved,
    its address/prefix and mask cannot change by re-allocating. A caller that supplies an
    explicit prefix length differing from the reserved one therefore gets a clear error rather
    than silently receiving the existing allocation. An absent or matching prefix length is a
    no-op and the existing reservation is reused.

    Raises:
        ValidationError: when an explicit prefix length conflicts with the reservation.

    """
    requested_prefixlen = prefixlen if prefixlen is not None else (data or {}).get("prefixlen")
    if requested_prefixlen is None:
        return

    existing_prefixlen = ipaddress.ip_interface(str(reserved_value)).network.prefixlen
    if requested_prefixlen != existing_prefixlen:
        raise ValidationError(
            input_value=(
                f"{pool_kind}: {pool_name} | This resource is already allocated as "
                f"{reserved_value}; its prefix length cannot be changed, only "
                f"/{existing_prefixlen} can be used."
            )
        )


def validate_reserved_kind(
    *,
    pool_kind: str,
    pool_name: str,
    reserved_value: Any,
    reserved_kind: str,
    requested_kind: str | None,
) -> None:
    """Guard re-allocation of an existing pool reservation against a conflicting target kind.

    The counterpart of validate_reserved_prefix_length for the allocated object's kind. A
    reservation's node keeps the kind it was created with, so a caller re-allocating the same
    identifier with an explicit, different kind gets a clear error rather than silently
    receiving a node of the original kind. An absent or matching kind is a no-op and the
    existing reservation is reused.

    Raises:
        ValidationError: when an explicit kind conflicts with the reservation.

    """
    if requested_kind is None or requested_kind == reserved_kind:
        return

    raise ValidationError(
        input_value=(
            f"{pool_kind}: {pool_name} | This resource is already allocated as "
            f"{reserved_value} of kind {reserved_kind}; its kind cannot be changed, only "
            f"{reserved_kind} can be used."
        )
    )

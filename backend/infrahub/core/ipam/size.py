from infrahub.core.node import Node

from .constants import PrefixMemberType


def get_prefix_space(ip_prefix: Node) -> int:
    prefix_space = ip_prefix.prefix.num_addresses  # type: ignore[attr-defined]

    # Non-RFC3021 subnet
    if (
        ip_prefix.member_type.value == PrefixMemberType.ADDRESS.value  # type: ignore[attr-defined]
        and ip_prefix.prefix.version == 4  # type: ignore[attr-defined]
        and ip_prefix.prefix.prefixlen < 31  # type: ignore[attr-defined]
        and not ip_prefix.is_pool.value  # type: ignore[attr-defined]
    ):
        prefix_space -= 2

    return prefix_space

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.ipam.constants import AnyBranch
from infrahub.core.query.ipam import (
    IPAddressData,
    IPPrefixData,
    IPPrefixIPAddressFetch,
    IPPrefixIPAddressFetchFree,
    IPPrefixSubnetFetch,
    IPPrefixSubnetFetchFree,
    IPv6PrefixIPAddressFetchFree,
    IPv6PrefixSubnetFetchFree,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.branch import Branch
    from infrahub.core.ipam.constants import IPAddressType, IPNetworkType
    from infrahub.core.protocols_base import CoreNode
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


def _query_branch(on_branch: Branch | AnyBranch) -> tuple[Branch, bool]:
    """Return the branch and the branch-agnostic flag that the free-value queries take for `on_branch`."""
    if isinstance(on_branch, AnyBranch):
        # The branch-agnostic query reads the window of every live branch, but every query still needs a branch.
        return registry.get_branch_from_registry(), True
    return on_branch, False


class IPAMResourceAllocator:
    """Allocator for IPAM resources (prefixes and addresses) within pools.

    This class provides optimized methods for finding the next available
    IP prefix or address within a parent prefix. It uses database-side
    Cypher computation for performance, which is especially important
    for IPv6 allocations where the address space is very large.

    Every method takes the namespace to read, given as a node, its ID, or None for the default namespace.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def _get_next_ipv4_prefix(
        self,
        ip_prefix: IPNetworkType,
        target_prefix_length: int,
        *,
        namespace: CoreNode | str | None,
        on_branch: Branch | AnyBranch,
        at: Timestamp | str | None = None,
        parent_uuid: str | None = None,
    ) -> IPNetworkType | None:
        """Get the next available free IPv4 prefix.

        Uses integer arithmetic in Cypher for efficient gap detection in the
        IPv4 address space.

        Args:
            ip_prefix: Parent prefix to allocate from.
            target_prefix_length: Desired prefix length for the new prefix (0-32).
            namespace: IP namespace node or its ID.
            on_branch: Branch whose values are taken, or `ANY_BRANCH` for the values any live branch holds.
            at: Optional timestamp for point-in-time queries.

        Returns:
            The next available IPv4 prefix, or None if no space is available
            or if the target_prefix_length is invalid.

        """
        if target_prefix_length < 0 or target_prefix_length > 32:
            return None
        if target_prefix_length < ip_prefix.prefixlen:
            return None

        branch, branch_agnostic = _query_branch(on_branch)
        query = await IPPrefixSubnetFetchFree.init(
            db=self.db,
            branch=branch,
            obj=ip_prefix,
            target_prefixlen=target_prefix_length,
            namespace=namespace,
            at=at,
            branch_agnostic=branch_agnostic,
            parent_uuid=parent_uuid,
        )
        await query.execute(db=self.db)

        result_data = query.get_prefix_data()
        if not result_data:
            return None

        network_address = ipaddress.IPv4Address(result_data.free_start)
        return ipaddress.ip_network(f"{network_address}/{target_prefix_length}")

    async def _get_next_ipv6_prefix(
        self,
        ip_prefix: IPNetworkType,
        target_prefix_length: int,
        *,
        namespace: CoreNode | str | None,
        on_branch: Branch | AnyBranch,
        at: Timestamp | str | None = None,
        parent_uuid: str | None = None,
    ) -> IPNetworkType | None:
        """Get the next available free IPv6 prefix.

        Uses binary string operations in Cypher to handle IPv6's 128-bit address
        space, as integer values would overflow Neo4j's 64-bit integer type.

        Args:
            ip_prefix: Parent prefix to allocate from.
            target_prefix_length: Desired prefix length for the new prefix (0-128).
            namespace: IP namespace node or its ID.
            on_branch: Branch whose values are taken, or `ANY_BRANCH` for the values any live branch holds.
            at: Optional timestamp for point-in-time queries.

        Returns:
            The next available IPv6 prefix, or None if no space is available
            or if the target_prefix_length is invalid.

        """
        if target_prefix_length < 0 or target_prefix_length > 128:
            return None
        if target_prefix_length < ip_prefix.prefixlen:
            return None

        branch, branch_agnostic = _query_branch(on_branch)
        query = await IPv6PrefixSubnetFetchFree.init(
            db=self.db,
            branch=branch,
            obj=ip_prefix,
            target_prefixlen=target_prefix_length,
            namespace=namespace,
            at=at,
            branch_agnostic=branch_agnostic,
            parent_uuid=parent_uuid,
        )
        await query.execute(db=self.db)

        result_data = query.get_prefix_data()
        if not result_data:
            return None

        # Convert binary string to IPv6 address
        addr_int = int(result_data.free_start_bin, 2)
        network_address = ipaddress.IPv6Address(addr_int)
        return ipaddress.ip_network(f"{network_address}/{target_prefix_length}")

    async def get_next_prefix(
        self,
        ip_prefix: IPNetworkType,
        target_prefix_length: int,
        *,
        namespace: CoreNode | str | None,
        on_branch: Branch | AnyBranch,
        at: Timestamp | str | None = None,
        parent_uuid: str | None = None,
    ) -> IPNetworkType | None:
        """Get the next available free prefix of specified length within a parent prefix.

        Automatically selects the appropriate method based on IP version (IPv4 vs IPv6).

        Args:
            ip_prefix: Parent prefix to allocate from.
            target_prefix_length: Desired prefix length for the new prefix.
            namespace: IP namespace node or its ID.
            on_branch: Branch whose values are taken, or `ANY_BRANCH` for the values any live branch holds.
            at: Optional timestamp for point-in-time queries.
            parent_uuid: UUID of the pool-resource prefix node to exclude from occupied ranges.

        Returns:
            The next available prefix, or None if no space is available.

        """
        if ip_prefix.version == 4:
            return await self._get_next_ipv4_prefix(
                ip_prefix=ip_prefix,
                target_prefix_length=target_prefix_length,
                namespace=namespace,
                on_branch=on_branch,
                at=at,
                parent_uuid=parent_uuid,
            )
        return await self._get_next_ipv6_prefix(
            ip_prefix=ip_prefix,
            target_prefix_length=target_prefix_length,
            namespace=namespace,
            on_branch=on_branch,
            at=at,
            parent_uuid=parent_uuid,
        )

    async def get_next_address(
        self,
        ip_prefix: IPNetworkType,
        *,
        namespace: CoreNode | str | None,
        on_branch: Branch | AnyBranch,
        at: Timestamp | str | None = None,
        is_pool: bool = False,
    ) -> IPAddressType | None:
        """Get the next available free IP address within a prefix.

        Automatically selects the appropriate query based on IP version (IPv4 vs IPv6).

        Args:
            ip_prefix: Prefix to allocate an address from.
            namespace: IP namespace node or its ID.
            on_branch: Branch whose values are taken, or `ANY_BRANCH` for the values any live branch holds.
            at: Optional timestamp for point-in-time queries.
            is_pool: If True, includes network and broadcast addresses as allocatable.
                If False (default), reserves the first and last addresses.

        Returns:
            The next available IP address, or None if no addresses are available.

        """
        branch, branch_agnostic = _query_branch(on_branch)
        # Use IPv6-specific query for IPv6 to avoid 64-bit integer overflow
        query_class = IPv6PrefixIPAddressFetchFree if ip_prefix.version == 6 else IPPrefixIPAddressFetchFree
        query = await query_class.init(
            db=self.db,
            branch=branch,
            obj=ip_prefix,
            namespace=namespace,
            at=at,
            branch_agnostic=branch_agnostic,
            is_pool=is_pool,
        )
        await query.execute(db=self.db)
        return query.get_address()

    async def get_subnets(
        self,
        ip_prefix: IPNetworkType,
        *,
        namespace: CoreNode | str | None,
        on_branch: Branch,
        at: Timestamp | str | None = None,
    ) -> Iterable[IPPrefixData]:
        """Get all subnets within a parent prefix on `on_branch`.

        Args:
            ip_prefix: Parent prefix to query.
            namespace: IP namespace node or its ID.
            at: Optional timestamp for point-in-time queries.

        Returns:
            Iterable of IPPrefixData objects representing child subnets.

        """
        query = await IPPrefixSubnetFetch.init(
            db=self.db,
            branch=on_branch,
            obj=ip_prefix,
            namespace=namespace,
            at=at,
        )
        await query.execute(db=self.db)
        return query.get_subnets()

    async def get_ip_addresses(
        self,
        ip_prefix: IPNetworkType,
        *,
        namespace: CoreNode | str | None,
        on_branch: Branch,
        at: Timestamp | str | None = None,
    ) -> Iterable[IPAddressData]:
        """Get all IP addresses within a prefix on `on_branch`.

        Args:
            ip_prefix: Prefix to query.
            namespace: IP namespace node or its ID.
            at: Optional timestamp for point-in-time queries.

        Returns:
            Iterable of IPAddressData objects representing addresses in the prefix.

        """
        query = await IPPrefixIPAddressFetch.init(
            db=self.db,
            branch=on_branch,
            obj=ip_prefix,
            namespace=namespace,
            at=at,
        )
        await query.execute(db=self.db)
        return query.get_addresses()

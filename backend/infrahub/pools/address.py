from netaddr import IPNetwork, IPSet

from infrahub.core.ipam.constants import IPAddressType, IPNetworkType


def get_available(network: IPNetworkType, addresses: list[IPAddressType], is_pool: bool) -> IPSet:
    pool = IPSet(IPNetwork(str(network)))
    reserved = [IPNetwork(f"{str(address.ip)}/{address.max_prefixlen}") for address in addresses]
    if not is_pool:
        # If the specified network is not a pool we remove the network address and
        # optionally the broadcast address in case of IPv4
        reserved.append(IPNetwork(f"{str(network.network_address)}/{network.max_prefixlen}"))
        if network.version == 4:
            reserved.append(IPNetwork(f"{str(network.broadcast_address)}/{network.max_prefixlen}"))

    return pool - IPSet(reserved)

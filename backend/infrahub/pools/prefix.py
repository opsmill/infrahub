from __future__ import annotations

import ipaddress
from collections import OrderedDict, defaultdict
from ipaddress import IPv4Network, IPv6Network
from typing import Optional, Union


class PrefixPool:
    """
    Class to automatically manage Prefixes and help to carve out sub-prefixes
    """

    def __init__(self, network: str):
        self.network = ipaddress.ip_network(network)

        # Define biggest and smallest possible masks
        self.mask_biggest = self.network.prefixlen + 1
        if self.network.version == 4:
            self.mask_smallest = 32
        else:
            self.mask_smallest = 128

        self.available_subnets = defaultdict(list)
        self.sub_by_key: dict[str, Optional[str]] = OrderedDict()
        self.sub_by_id: dict[str, str] = OrderedDict()

        # Save the top level available subnet
        for subnet in list(self.network.subnets(new_prefix=self.mask_biggest)):
            self.available_subnets[self.mask_biggest].append(str(subnet))

    def reserve(self, subnet: str, identifier: Optional[str] = None) -> bool:
        """
        Indicate that a specific subnet is already reserved/used
        """

        # TODO Add check to make sure the subnet provided has the right size
        sub = ipaddress.ip_network(subnet)

        if int(sub.prefixlen) <= int(self.network.prefixlen):
            raise ValueError(f"{subnet} do not have the right size ({sub.prefixlen},{self.network.prefixlen})")

        if sub.supernet(new_prefix=self.network.prefixlen) != self.network:
            raise ValueError(f"{subnet} is not part of this network")

        # Check first if this ID as already done a reservation
        if identifier and identifier in self.sub_by_id.keys():
            if self.sub_by_id[identifier] == str(sub):
                return True
            raise ValueError(
                f"this identifier ({identifier}) is already used but for a different resource ({self.sub_by_id[identifier]})"
            )

        if identifier and str(sub) in self.sub_by_key.keys():
            raise ValueError(f"this subnet is already reserved but not with this identifier ({identifier})")

        if str(sub) in self.sub_by_key.keys():
            self.remove_subnet_from_available_list(sub)
            return True

        # Check if the subnet itself is available
        # if available reserve and return
        if subnet in self.available_subnets[sub.prefixlen]:
            if identifier:
                self.sub_by_id[identifier] = subnet
                self.sub_by_key[subnet] = identifier
            else:
                self.sub_by_key[subnet] = None

            self.remove_subnet_from_available_list(sub)
            return True

        # If not reserved already, check if the subnet is available
        # start at sublen and check all available subnet
        # increase 1 by 1 until we find the closer supernet available
        # break it down and keep track of the other available subnets

        for sublen in range(sub.prefixlen - 1, self.network.prefixlen, -1):
            supernet = sub.supernet(new_prefix=sublen)
            if str(supernet) in self.available_subnets[sublen]:
                self.split_supernet(supernet=supernet, subnet=sub)
                return self.reserve(subnet=subnet, identifier=identifier)

        return False

    def get(self, size: int, identifier: Optional[str] = None) -> Union[IPv4Network, IPv6Network]:
        """Return the next available Subnet."""

        clean_size = int(size)

        if identifier and identifier in self.sub_by_id.keys():
            net = ipaddress.ip_network(self.sub_by_id[identifier])
            if net.prefixlen == clean_size:
                return net
            raise ValueError()

        if len(self.available_subnets[clean_size]) != 0:
            sub = self.available_subnets[clean_size][0]
            self.reserve(subnet=sub, identifier=identifier)
            return ipaddress.ip_network(sub)

        # if a subnet of this size is not available
        # we need to find the closest subnet available and split it
        for i in range(clean_size - 1, self.mask_biggest - 1, -1):
            if len(self.available_subnets[i]) != 0:
                supernet = ipaddress.ip_network(self.available_subnets[i][0])
                # supernet available, will split it
                subs = supernet.subnets(new_prefix=clean_size)
                next_sub: Union[IPv4Network, IPv6Network] = next(subs)  # type: ignore[assignment]
                self.split_supernet(supernet=supernet, subnet=next_sub)
                self.reserve(subnet=str(next_sub), identifier=identifier)
                return next_sub

        raise IndexError("No More subnet available")

    def get_nbr_available_subnets(self) -> dict[int, int]:
        tmp = {}
        for i in range(self.mask_biggest, self.mask_smallest + 1):
            tmp[i] = len(self.available_subnets[i])

        return tmp

    def check_if_already_allocated(self, identifier: str) -> bool:
        """
        Check if a subnet has already been allocated based on an identifier

        Need to add the same capability based on Network address
        If both identifier and subnet are provided, identifier take precedence
        """
        if identifier in self.sub_by_id.keys():
            return True
        return False

    def split_supernet(
        self, supernet: Union[IPv4Network, IPv6Network], subnet: Union[IPv4Network, IPv6Network]
    ) -> None:
        """Split a supernet into smaller networks"""

        # TODO ensure subnet is small than supernet
        # TODO ensure that subnet is part of supernet
        parent_net = supernet
        for i in range(supernet.prefixlen + 1, subnet.prefixlen + 1):
            tmp_net: list[Union[IPv4Network, IPv6Network]] = list(parent_net.subnets(new_prefix=i))

            if i == subnet.prefixlen:
                for net in tmp_net:
                    self.available_subnets[i].append(str(net))
            else:
                if subnet.subnet_of(other=tmp_net[0]):  # type: ignore[arg-type]
                    parent = 0
                    other = 1
                else:
                    parent = 1
                    other = 0

                parent_net = tmp_net[parent]
                self.available_subnets[i].append(str(tmp_net[other]))

        self.remove_subnet_from_available_list(supernet)

    def remove_subnet_from_available_list(self, subnet: Union[IPv4Network, IPv6Network]) -> None:
        """Remove a subnet from the list of available Subnet."""

        idx = self.available_subnets[subnet.prefixlen].index(str(subnet))
        del self.available_subnets[subnet.prefixlen][idx]

        # if idx:
        #     return True
        # except:
        #     log.warn("Unable to remove %s from list of available subnets" % str(subnet))
        #     return False

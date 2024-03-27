from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING, List, Optional, Union

from infrahub.core.constants import InfrahubKind
from infrahub.core.query import Query
from infrahub.core.registry import registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class IPPrefixSubnetFetch(Query):
    name: str = "ipprefix_subnet_fetch"

    def __init__(self, ip_prefix, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = """
        MATCH (pfx:%s)-[HAS_ATTRIBUTE]-(an:Attribute {name: "prefix"})-[HAS_VALUE]-(av:AttributeValue)
        """ % (InfrahubKind.IPPREFIX)

        self.add_to_query(query)
        self.return_labels = ["pfx", "av"]

    def get_subnets(self):
        """Return a list of all subnets fitting in the prefix."""
        subnets = []

        for result in self.get_results():
            prefix = ipaddress.ip_network(result.get("av").get("value"))
            if self.ip_prefix.prefix.version != prefix.version:
                continue
            if not prefix.subnet_of(ipaddress.ip_network(self.ip_prefix.prefix.value)):
                continue

            subnets.append(prefix)  # FIXME: these should be nodes

        return subnets


class IPPrefixIPAddressFetch(Query):
    name: str = "ipprefix_ipaddress_fetch"

    def __init__(self, ip_prefix, *args, **kwargs):
        self.ip_prefix = ip_prefix
        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args, **kwargs):
        query = """
        MATCH (addr:%s)-[HAS_ATTRIBUTE]-(an:Attribute {name: "address"})-[HAS_VALUE]-(av:AttributeValue)
        """ % (InfrahubKind.IPADDRESS)

        self.add_to_query(query)
        self.return_labels = ["addr", "av"]

    def get_addresses(self):
        """Return a list of all addresses fitting in the prefix."""
        addresses = []

        for result in self.get_results():
            address = ipaddress.ip_interface(result.get("av").get("value"))
            if self.ip_prefix.prefix.version != address.version:
                continue
            if address not in ipaddress.ip_network(self.ip_prefix.prefix.value):
                continue

            addresses.append(address)  # FIXME: these should be nodes

        return addresses


async def get_subnets(
    ip_prefix, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> List[str]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixSubnetFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_subnets()


async def get_ip_addresses(
    ip_prefix, db: InfrahubDatabase, branch: Optional[Union[Branch, str]] = None, at=None
) -> List[str]:
    branch = await registry.get_branch(db=db, branch=branch)
    query = await IPPrefixIPAddressFetch.init(db=db, branch=branch, ip_prefix=ip_prefix, at=at)
    await query.execute(db=db)
    return query.get_addresses()

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipStatus
from infrahub.core.query import Query

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class IPAddressPoolGetIdentifiers(Query):
    name: str = "ipaddresspool_get_identifiers"

    def __init__(
        self,
        *args: Any,
        pool_id: str,
        allocated: list[str],
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.addresses = allocated

        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: dict[str, Any]) -> None:
        self.params["pool_id"] = self.pool_id
        self.params["addresses"] = self.addresses

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPAddress)
        WHERE allocated.uuid in $addresses
        """ % {"ipaddress_pool": InfrahubKind.IPADDRESSPOOL}
        self.add_to_query(query)
        self.return_labels = ["allocated", "reservation"]


class IPAddressPoolGetReserved(Query):
    name: str = "ipaddresspool_get_reserved"

    def __init__(
        self,
        *args: Any,
        pool_id: str,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: dict[str, Any]) -> None:
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[rel:IS_RESERVED]->(address:BuiltinIPAddress)
        WHERE rel.identifier = $identifier
        """ % {"ipaddress_pool": InfrahubKind.IPADDRESSPOOL}
        self.add_to_query(query)
        self.return_labels = ["address"]


class IPAddressPoolSetReserved(Query):
    name: str = "ipaddresspool_set_reserved"

    def __init__(
        self,
        pool_id: str,
        address_id: str,
        identifier: str,
        *args: Any,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.address_id = address_id
        self.identifier = identifier

        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: dict[str, Any]) -> None:
        self.params["pool_id"] = self.pool_id
        self.params["address_id"] = self.address_id
        self.params["identifier"] = self.identifier

        global_branch = registry.get_global_branch()
        self.params["rel_prop"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "identifier": self.identifier,
        }

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })
        MATCH (address:Node { uuid: $address_id })
        CREATE (pool)-[rel:IS_RESERVED $rel_prop]->(address)
        """ % {"ipaddress_pool": InfrahubKind.IPADDRESSPOOL}

        self.add_to_query(query)
        self.return_labels = ["pool", "rel", "address"]


class PrefixPoolGetIdentifiers(Query):
    name: str = "prefixpool_get_identifiers"

    def __init__(
        self,
        *args: Any,
        pool_id: str,
        allocated: list[str],
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.prefixes = allocated

        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: dict[str, Any]) -> None:
        self.params["pool_id"] = self.pool_id
        self.params["prefixes"] = self.prefixes

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPPrefix)
        WHERE allocated.uuid in $prefixes
        """ % {"ipaddress_pool": InfrahubKind.IPPREFIXPOOL}
        self.add_to_query(query)
        self.return_labels = ["allocated", "reservation"]


class PrefixPoolGetReserved(Query):
    name: str = "prefixpool_get_reserved"

    def __init__(
        self,
        *args: Any,
        pool_id: str,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: dict[str, Any]) -> None:
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier

        query = """
        MATCH (pool:%(prefix_pool)s { uuid: $pool_id })-[rel:IS_RESERVED]->(prefix:BuiltinIPPrefix)
        WHERE rel.identifier = $identifier
        """ % {"prefix_pool": InfrahubKind.IPPREFIXPOOL}
        self.add_to_query(query)
        self.return_labels = ["prefix"]


class PrefixPoolSetReserved(Query):
    name: str = "prefixpool_set_reserved"

    def __init__(
        self,
        pool_id: str,
        prefix_id: str,
        identifier: str,
        *args: Any,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.prefix_id = prefix_id
        self.identifier = identifier

        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: dict[str, Any]) -> None:
        self.params["pool_id"] = self.pool_id
        self.params["prefix_id"] = self.prefix_id
        self.params["identifier"] = self.identifier

        global_branch = registry.get_global_branch()
        self.params["rel_prop"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "identifier": self.identifier,
        }

        query = """
        MATCH (pool:%(prefix_pool)s { uuid: $pool_id })
        MATCH (prefix:Node { uuid: $prefix_id })
        CREATE (pool)-[rel:IS_RESERVED $rel_prop]->(prefix)
        """ % {"prefix_pool": InfrahubKind.IPPREFIXPOOL}

        self.add_to_query(query)
        self.return_labels = ["pool", "rel", "prefix"]

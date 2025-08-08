from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generator

from pydantic import BaseModel, ConfigDict

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipStatus
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.database import InfrahubDatabase


class NumberPoolIdentifierData(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: int
    identifier: str


class IPAddressPoolGetIdentifiers(Query):
    name = "ipaddresspool_get_identifiers"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        allocated: list[str],
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.addresses = allocated

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["addresses"] = self.addresses

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPAddress)
        WHERE allocated.uuid in $addresses
        """ % {"ipaddress_pool": InfrahubKind.IPADDRESSPOOL}
        self.add_to_query(query)
        self.return_labels = ["allocated", "reservation"]


class IPAddressPoolGetReserved(Query):
    name = "ipaddresspool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[rel:IS_RESERVED]->(address:BuiltinIPAddress)
        WHERE rel.identifier = $identifier
        """ % {"ipaddress_pool": InfrahubKind.IPADDRESSPOOL}
        self.add_to_query(query)
        self.return_labels = ["address"]


class IPAddressPoolSetReserved(Query):
    name = "ipaddresspool_set_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        pool_id: str,
        address_id: str,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.address_id = address_id
        self.identifier = identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
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


class NumberPoolGetAllocated(Query):
    name = "numberpool_get_allocated"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool = pool

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["node_attribute"] = self.pool.node_attribute.value
        self.params["start_range"] = self.pool.start_range.value
        self.params["end_range"] = self.pool.end_range.value
        self.params["pool_id"] = self.pool.get_id()

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH (n:%(node)s)-[ha:HAS_ATTRIBUTE]-(a:Attribute {name: $node_attribute})-[hv:HAS_VALUE]-(av:AttributeValueIndexed)
        MATCH (a)-[hs:HAS_SOURCE]-(pool:%(number_pool_kind)s)
        WHERE
            pool.uuid = $pool_id
            AND av.value >= $start_range and av.value <= $end_range
            AND all(r in [ha, hv, hs] WHERE (%(branch_filter)s))
            AND ha.status = "active"
            AND hv.status = "active"
            AND hs.status = "active"
        """ % {
            "node": self.pool.node.value,
            "number_pool_kind": InfrahubKind.NUMBERPOOL,
            "branch_filter": branch_filter,
        }
        self.add_to_query(query)

        self.return_labels = ["n.uuid as id", "hv.branch as branch", "av.value as value"]
        self.order_by = ["av.value"]


class NumberPoolGetReserved(Query):
    name = "numberpool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )

        self.params.update(branch_params)

        # If identifier is not provided, we return all reservations for the pool
        identifier_filter = ""
        if self.identifier:
            identifier_filter = "r.identifier = $identifier AND "
            self.params["identifier"] = self.identifier

        query = """
        MATCH (pool:%(number_pool)s { uuid: $pool_id })-[r:IS_RESERVED]->(reservation:AttributeValue)
        WHERE
            %(identifier_filter)s
            %(branch_filter)s
        """ % {
            "branch_filter": branch_filter,
            "number_pool": InfrahubKind.NUMBERPOOL,
            "identifier_filter": identifier_filter,
        }
        self.add_to_query(query)
        self.return_labels = ["reservation.value AS value", "r.identifier AS identifier"]

    def get_reservation(self) -> int | None:
        result = self.get_result()
        if result:
            return result.get_as_optional_type("value", return_type=int)
        return None

    def get_reservations(self) -> Generator[NumberPoolIdentifierData]:
        for result in self.results:
            yield NumberPoolIdentifierData.model_construct(
                value=result.get_as_type("value", return_type=int),
                identifier=result.get_as_type("identifier", return_type=str),
            )


class PoolChangeReserved(Query):
    """Change the identifier on all pools.
    This is useful when a node is being converted to a different type and its ID has changed
    """

    name = "pool_change_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        existing_identifier: str,
        new_identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.existing_identifier = existing_identifier
        self.new_identifier = new_identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["new_identifier"] = self.new_identifier
        self.params["existing_identifier"] = self.existing_identifier
        self.params["at"] = self.at.to_string()

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )

        self.params.update(branch_params)

        global_branch = registry.get_global_branch()
        self.params["rel_prop"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "identifier": self.new_identifier,
        }

        query = """
        MATCH (pool:Node)-[r:IS_RESERVED]->(resource)
        WHERE
            r.identifier = $existing_identifier
            AND
            %(branch_filter)s
        SET r.to = $at
        CREATE (pool)-[new_rel:IS_RESERVED $rel_prop]->(resource)
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["pool.uuid AS pool_id", "r", "new_rel"]


"""
Important!: The relationship IS_RESERVED for Number is not being cleaned up when the node or the branch is deleted
I think this is something we should address in the future.
It works for now because the query has been updated to match the identifier in IS_RESERVED with the UUID of the related node
But in the future, if we need to use an identifier that is not the UUID, we will need to clean up the relationships
This will be especially important as we want to support upsert with NumberPool
"""


class NumberPoolGetUsed(Query):
    name = "number_pool_get_used"
    type = QueryType.READ
    return_model = NumberPoolIdentifierData

    def __init__(
        self,
        pool: CoreNumberPool,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool = pool

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool.get_id()
        self.params["start_range"] = self.pool.start_range.value
        self.params["end_range"] = self.pool.end_range.value

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )

        self.params.update(branch_params)
        self.params["attribute_name"] = self.pool.node_attribute.value

        query = """
        MATCH (pool:%(number_pool)s { uuid: $pool_id })-[res:IS_RESERVED]->(av:AttributeValueIndexed)
        WHERE toInteger(av.value) >= $start_range and toInteger(av.value) <= $end_range
        CALL (pool, res, av) {
            MATCH (pool)-[res]->(av)<-[hv:HAS_VALUE]-(attr:Attribute)<-[ha:HAS_ATTRIBUTE]-(n:%(node)s)
            WHERE
                n.uuid = res.identifier AND
                attr.name = $attribute_name AND
                all(r in [res, hv, ha] WHERE (%(branch_filter)s))
            ORDER BY res.branch_level DESC, hv.branch_level DESC, ha.branch_level DESC, res.from DESC, hv.from DESC, ha.from DESC
            RETURN (res.status = "active" AND hv.status = "active" AND ha.status = "active") AS is_active
            LIMIT 1
        }
        WITH av, res, is_active
        WHERE is_active = True
        """ % {
            "branch_filter": branch_filter,
            "number_pool": InfrahubKind.NUMBERPOOL,
            "node": self.pool.node.value,
        }

        self.add_to_query(query)
        self.return_labels = ["DISTINCT(av.value) as value", "res.identifier as identifier"]
        self.order_by = ["value"]

    def iter_results(self) -> Generator[NumberPoolIdentifierData]:
        for result in self.results:
            yield self.return_model.model_construct(
                value=result.get_as_type("value", return_type=int),
                identifier=result.get_as_type("identifier", return_type=str),
            )


class NumberPoolSetReserved(Query):
    name = "numberpool_set_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        pool_id: str,
        reserved: int,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.reserved = reserved
        self.identifier = identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["reserved"] = self.reserved
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
        MATCH (pool:%(number_pool)s { uuid: $pool_id })
        MERGE (value:AttributeValue:AttributeValueIndexed { value: $reserved, is_default: false })
        WITH value, pool
        LIMIT 1
        CREATE (pool)-[rel:IS_RESERVED $rel_prop]->(value)
        """ % {"number_pool": InfrahubKind.NUMBERPOOL}

        self.add_to_query(query)
        self.return_labels = ["value"]


class PrefixPoolGetIdentifiers(Query):
    name = "prefixpool_get_identifiers"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        allocated: list[str],
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.prefixes = allocated

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["prefixes"] = self.prefixes

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPPrefix)
        WHERE allocated.uuid in $prefixes
        """ % {"ipaddress_pool": InfrahubKind.IPPREFIXPOOL}
        self.add_to_query(query)
        self.return_labels = ["allocated", "reservation"]


class PrefixPoolGetReserved(Query):
    name = "prefixpool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier

        query = """
        MATCH (pool:%(prefix_pool)s { uuid: $pool_id })-[rel:IS_RESERVED]->(prefix:BuiltinIPPrefix)
        WHERE rel.identifier = $identifier
        """ % {"prefix_pool": InfrahubKind.IPPREFIXPOOL}
        self.add_to_query(query)
        self.return_labels = ["prefix"]


class PrefixPoolSetReserved(Query):
    name = "prefixpool_set_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        pool_id: str,
        prefix_id: str,
        identifier: str,
        **kwargs: dict[str, Any],
    ) -> None:
        self.pool_id = pool_id
        self.prefix_id = prefix_id
        self.identifier = identifier

        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
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

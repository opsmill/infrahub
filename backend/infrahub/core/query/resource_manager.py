from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Generator, Unpack

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RelationshipStatus
from infrahub.core.query import Query, QueryInitKwargs, QueryResult, QueryType

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.database import InfrahubDatabase


class PoolRecordProvenance(StrEnum):
    """How the number the attribute currently holds got there."""

    ALLOCATED = "allocated"
    PROVIDED = "provided"


@dataclass(frozen=True)
class NumberPoolIdentifierData:
    """Result containing a pool reservation value and its identifier."""

    value: int
    identifier: str


@dataclass(frozen=True)
class PoolIdentifierResult:
    """Result from pool identifier queries containing allocation and identifier data."""

    allocated_uuid: str
    """UUID of the allocated resource (address or prefix)."""

    identifier: str
    """Identifier used for the reservation."""

    @classmethod
    def from_db(cls, result: QueryResult) -> PoolIdentifierResult:
        """Convert raw QueryResult to typed dataclass."""
        return cls(
            allocated_uuid=result.get_as_type("allocated_uuid", str),
            identifier=result.get_as_type("identifier", str),
        )


@dataclass(frozen=True)
class NumberPoolAllocatedResult:
    """Result from NumberPoolGetAllocated containing allocated number info."""

    id: str
    """UUID of the node with the allocated number."""

    branch: str
    """Branch where the allocation exists."""

    value: int
    """The allocated number value."""

    identifier: str
    """Identifier used for the reservation."""


@dataclass(frozen=True)
class NumberPoolFreeData:
    value: int
    is_free: bool
    is_last: bool

    @classmethod
    def from_db(cls, result: QueryResult) -> NumberPoolFreeData:
        return cls(
            value=result.get_as_type("value", return_type=int),
            is_free=result.get_as_type("is_free", return_type=bool),
            is_last=result.get_as_type("is_last", return_type=bool),
        )


class IPAddressPoolGetIdentifiers(Query):
    name = "ipaddresspool_get_identifiers"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        allocated: list[str],
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.addresses = allocated

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["addresses"] = self.addresses

        query = """
        MATCH (pool:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPAddress)
        WHERE allocated.uuid in $addresses
        """ % {"ipaddress_pool": InfrahubKind.IPADDRESSPOOL}
        self.add_to_query(query)
        self.return_labels = ["allocated.uuid AS allocated_uuid", "reservation.identifier AS identifier"]

    def get_data(self) -> list[PoolIdentifierResult]:
        """Return results as typed dataclass instances.

        Returns:
            List of PoolIdentifierResult containing allocation and identifier data.

        """
        return [PoolIdentifierResult.from_db(result) for result in self.get_results()]


class IPAddressPoolGetReserved(Query):
    name = "ipaddresspool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
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
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.address_id = address_id
        self.identifier = identifier

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
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
    """Report each number the pool has allocated together with the branch that holds it.

    Reports any active value on any branch for the given NumberPool along with its parent object ID,
    branch, and reservation identifier.
    """

    name = "numberpool_get_allocated"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["node_attribute"] = self.pool.node_attribute.value
        self.params["start_range"] = self.pool.start_range.value
        self.params["end_range"] = self.pool.end_range.value
        self.params["pool_id"] = self.pool.get_id()

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH (pool:Node:%(number_pool_kind)s { uuid: $pool_id })-[ir:IS_RESERVED]->(a:Attribute {name: $node_attribute})
        MATCH (n:%(node)s)-[ha:HAS_ATTRIBUTE]->(a)-[hv:HAS_VALUE]->(av:AttributeValueIndexed)
        WHERE
            av.value >= $start_range and av.value <= $end_range
            AND all(r in [ha, hv, ir] WHERE (%(branch_filter)s))
            AND ha.status = "active"
            AND hv.status = "active"
            AND ir.status = "active"
        """ % {
            "node": self.pool.node.value,
            "number_pool_kind": InfrahubKind.NUMBERPOOL,
            "branch_filter": branch_filter,
        }
        self.add_to_query(query)

        self.return_labels = [
            "DISTINCT n.uuid as id",
            "hv.branch as branch",
            "av.value as value",
            "ir.identifier as identifier",
        ]
        self.order_by = ["av.value"]

    def get_data(self) -> list[NumberPoolAllocatedResult]:
        """Return results as typed dataclass instances.

        Returns:
            List of NumberPoolAllocatedResult containing allocated number info.

        """
        return [
            NumberPoolAllocatedResult(
                id=result.get_as_type("id", str),
                branch=result.get_as_type("branch", str),
                value=result.get_as_type("value", int),
                identifier=result.get_as_type("identifier", str),
            )
            for result in self.get_results()
        ]


class NumberPoolGetReserved(Query):
    """Resolve a pool's reservation(s) to the value(s) on this branch.

    Returns the values and identifiers for a given NumberPools reservations on a given branch. Can
    optionally be filtered by identifier.
    """

    name = "numberpool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier
        self.params["at"] = self.at.to_string()

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })-[r_edge:IS_RESERVED]->(attr:Attribute)
        WHERE ($identifier IS NULL OR r_edge.identifier = $identifier)
        WITH DISTINCT pool, attr
        CALL (pool, attr) {
            // --------
            // assumes IS_RESERVED is on the global branch
            // --------
            MATCH (pool)-[r:IS_RESERVED]->(attr)
            WHERE ($identifier IS NULL OR r.identifier = $identifier)
            AND r.from <= $at AND (r.to IS NULL OR r.to > $at)
            ORDER BY r.from DESC, r.status ASC
            RETURN r.status = "active" AS is_active, r.identifier AS identifier
            LIMIT 1
        }
        WITH pool, attr, identifier
        WHERE is_active = TRUE
        CALL (attr) {
            MATCH (attr)-[r:HAS_VALUE]->(av)
            WHERE %(branch_filter)s
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            RETURN av.value AS value, r.status = "active" AS is_active
            LIMIT 1
        }
        WITH value, identifier, is_active
        WHERE is_active = TRUE
        """ % {
            "branch_filter": branch_filter,
            "number_pool": InfrahubKind.NUMBERPOOL,
        }
        self.add_to_query(query)
        self.return_labels = ["value", "identifier"]

    def get_reservation(self) -> int | None:
        """Return the value a single record resolves to.

        Returns:
            The reserved integer value, or None if no live record resolves to one.

        """
        result = self.get_result()
        if result:
            return result.get_as_optional_type("value", return_type=int)
        return None

    def get_data(self) -> list[NumberPoolIdentifierData]:
        """Return all reservations as typed dataclass instances.

        Returns:
            List of NumberPoolIdentifierData containing value and identifier.

        """
        return [
            NumberPoolIdentifierData(
                value=result.get_as_type("value", return_type=int),
                identifier=result.get_as_type("identifier", return_type=str),
            )
            for result in self.get_results()
        ]


class PoolChangeReserved(Query):
    """Change the identifier on all pools.

    This is useful when a node is being converted to a different type and its ID has changed.
    """

    name = "pool_change_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        existing_identifier: str,
        new_identifier: str,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.existing_identifier = existing_identifier
        self.new_identifier = new_identifier

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
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


def reserved_values_query() -> str:
    """Cypher fragment to find all Attributes reserved for a given NumberPool

    Finds every active value of each reserved Attribute on every non-deleting branch.

    Final values are res (IS_RESERVED edge) and value (an active Attribute value).
    """
    return """
    MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })-[res:IS_RESERVED]->(attr:Attribute { name: $attribute_name })
    WHERE res.status = "active" AND res.from <= $at AND (res.to IS NULL OR res.to > $at)
    MATCH (attr)-[hv:HAS_VALUE]->(av:AttributeValueIndexed)
    WHERE hv.status = "active"
      AND hv.from <= $at AND (hv.to IS NULL OR hv.to > $at)
      AND NOT EXISTS {
          MATCH (deleting:Branch { name: hv.branch })
          WHERE deleting.status = "DELETING"
      }
    WITH DISTINCT res, av.value AS value
    """ % {"number_pool": InfrahubKind.NUMBERPOOL}


class NumberPoolGetUsed(Query):
    """A pool is branch-agnostic, and so is the set of numbers it accounts for.

    The read carries no branch filter at all: the record is global, and a value counts while any
    branch holds it.
    """

    name = "number_pool_get_used"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool.get_id()
        self.params["start_range"] = self.pool.start_range.value
        self.params["end_range"] = self.pool.end_range.value

        self.params["attribute_name"] = self.pool.node_attribute.value
        self.params["at"] = self.at.to_string()

        query = """
        %(reserved_values)s
        WHERE toInteger(value) >= $start_range and toInteger(value) <= $end_range
        """ % {
            "reserved_values": reserved_values_query(),
        }

        self.add_to_query(query)
        self.return_labels = ["DISTINCT(value) as value", "res.identifier as identifier"]
        self.order_by = ["value"]

    def iter_results(self) -> Generator[NumberPoolIdentifierData]:
        """Yield used pool values as typed dataclass instances.

        Yields:
            NumberPoolIdentifierData for each used value in the pool.

        """
        for result in self.get_results():
            yield NumberPoolIdentifierData(
                value=result.get_as_type("value", return_type=int),
                identifier=result.get_as_type("identifier", return_type=str),
            )


class NumberPoolGetFree(Query):
    """A pool is branch-agnostic, and so is the set of numbers it accounts for.

    The read carries no branch filter at all: the record is global, and a value counts while any
    branch holds it.
    """

    name = "number_pool_get_free"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        min_value: int | None = None,
        max_value: int | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.min_value = min_value
        self.max_value = max_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool.get_id()
        # Use min_value/max_value if provided, otherwise use pool's start_range/end_range
        self.params["start_range"] = self.min_value if self.min_value is not None else self.pool.start_range.value
        self.params["end_range"] = self.max_value if self.max_value is not None else self.pool.end_range.value
        self.limit = 1  # Query only works at returning a single, free entry

        self.params["attribute_name"] = self.pool.node_attribute.value
        self.params["at"] = self.at.to_string()

        query = """
        %(reserved_values)s
        WHERE toInteger(value) >= $start_range and toInteger(value) <= $end_range
        WITH DISTINCT toInteger(value) AS used_value
        ORDER BY used_value ASC
        WITH [$start_range - 1] + collect(used_value) AS nums
        UNWIND range(0, size(nums) - 1) AS idx
        CALL (nums, idx) {
            WITH nums[idx] AS curr, idx - 1 + $start_range AS expected
            RETURN expected AS number, expected <> curr AS is_free, idx = size(nums) - 1 AS is_last
        }
        WITH number, is_free, is_last
        WHERE is_free = true OR is_last = true
        WITH number AS free_number, is_free, is_last
        """ % {
            "reserved_values": reserved_values_query(),
        }

        self.add_to_query(query)
        self.return_labels = ["free_number as value", "is_free", "is_last"]
        self.order_by = ["value"]

    def get_free_data(self) -> NumberPoolFreeData | None:
        if not self.results:
            return None

        return NumberPoolFreeData.from_db(result=self.results[0])

    def get_result_value(self) -> int | None:
        """Get the free number from query results, handling edge cases.

        Returns:
            The free number if found, None if pool is exhausted in queried range.

        """
        result_data = self.get_free_data()
        if result_data is None:
            # No reservations in range - return start_range
            if self.params["start_range"] <= self.params["end_range"]:
                return self.params["start_range"]
            return None

        if result_data.is_free:
            return result_data.value
        # is_last=True and is_free=False means all numbers up to value are used
        if result_data.is_last and result_data.value < self.params["end_range"]:
            return result_data.value + 1
        return None


class NumberPoolGetTaken(Query):
    """Values held on the target kind for the pool's attribute, whatever set them.

    Sees values created outside the pool, which allocation must skip or it stalls on a value the
    uniqueness constraint rejects.
    """

    name = "number_pool_get_taken"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        min_value: int | None = None,
        max_value: int | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.min_value = min_value
        self.max_value = max_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["start_range"] = self.min_value if self.min_value is not None else self.pool.start_range.value
        self.params["end_range"] = self.max_value if self.max_value is not None else self.pool.end_range.value

        # is_isolated=False mirrors the uniqueness validator: a value added to the origin branch after
        # this branch point still collides here.
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )

        self.params.update(branch_params)
        self.params["attribute_name"] = self.pool.node_attribute.value

        query = """
        MATCH (n:%(node)s)-[:HAS_ATTRIBUTE]->(attr:Attribute { name: $attribute_name })-[:HAS_VALUE]->(av:AttributeValueIndexed)
        WHERE av.value >= $start_range and av.value <= $end_range
        WITH DISTINCT n, attr
        CALL (n, attr) {
            MATCH (n)-[ha:HAS_ATTRIBUTE]->(attr)-[hv:HAS_VALUE]->(av:AttributeValueIndexed)
            WHERE all(r in [ha, hv] WHERE (%(branch_filter)s))
            ORDER BY ha.branch_level DESC, hv.branch_level DESC,
                ha.from DESC, hv.from DESC,
                ha.status ASC, hv.status ASC
            RETURN av.value AS value, (ha.status = "active" AND hv.status = "active") AS is_active
            LIMIT 1
        }
        WITH value, is_active
        WHERE is_active = True AND value >= $start_range AND value <= $end_range
        WITH DISTINCT value
        """ % {
            "branch_filter": branch_filter,
            "node": self.pool.node.value,
        }

        self.add_to_query(query)
        self.return_labels = ["value"]
        self.order_by = ["value"]

    def get_taken_values(self) -> set[int]:
        return {result.get_as_type("value", return_type=int) for result in self.get_results()}


class NumberPoolSetReserved(Query):
    """Record that a number pool accounts for an attribute.

    Check if the requested reservation already exists. If not, or if the provenance differs, then
    close the active reservation and create the new one.
    """

    name = "numberpool_set_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        attribute_id: str,
        provenance: PoolRecordProvenance,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier
        self.attribute_id = attribute_id
        self.provenance = provenance

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier
        self.params["at"] = self.at.to_string()
        self.params["provenance"] = self.provenance.value
        # A record written before provenance existed carries none, and an absent provenance already
        # reads as an allocation.
        self.params["allocated_provenance"] = PoolRecordProvenance.ALLOCATED.value
        self.params["attribute_id"] = self.attribute_id

        global_branch = registry.get_global_branch()
        self.params["rel_prop"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "identifier": self.identifier,
            "provenance": self.provenance.value,
        }

        query = """
        // ----------
        // Get the NumberPool and Attribute we are interested in
        // ----------
        MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })
        MATCH (attr:Attribute { uuid: $attribute_id })
        WITH pool, attr
        LIMIT 1
        // ----------
        // Only continue if the expected reservation is not active, accounting for change of provenance
        // ----------
        WHERE NOT EXISTS {
            MATCH (pool)-[mine:IS_RESERVED]->(attr)
            WHERE mine.status = "active" AND mine.to IS NULL
              AND coalesce(mine.provenance, $allocated_provenance) = $provenance
        }
        // ----------
        // Close any active reservations
        // ----------
        OPTIONAL MATCH ()-[live:IS_RESERVED]->(attr)
        WHERE live.status = "active" AND live.to IS NULL
        SET live.to = $at
        WITH DISTINCT pool, attr
        LIMIT 1
        // ----------
        // Create the new reservation
        // ----------
        CREATE (pool)-[rel:IS_RESERVED $rel_prop]->(attr)
        """ % {"number_pool": InfrahubKind.NUMBERPOOL}

        self.add_to_query(query)
        self.return_labels = ["attr.uuid AS attribute_id", "rel"]


class PrefixPoolGetIdentifiers(Query):
    name = "prefixpool_get_identifiers"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        allocated: list[str],
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.prefixes = allocated

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["prefixes"] = self.prefixes

        query = """
        MATCH (pool:Node:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPPrefix)
        WHERE allocated.uuid in $prefixes
        """ % {"ipaddress_pool": InfrahubKind.IPPREFIXPOOL}
        self.add_to_query(query)
        self.return_labels = ["allocated.uuid AS allocated_uuid", "reservation.identifier AS identifier"]

    def get_data(self) -> list[PoolIdentifierResult]:
        """Return results as typed dataclass instances.

        Returns:
            List of PoolIdentifierResult containing allocation and identifier data.

        """
        return [PoolIdentifierResult.from_db(result) for result in self.get_results()]


class PrefixPoolGetReserved(Query):
    name = "prefixpool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
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
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.prefix_id = prefix_id
        self.identifier = identifier

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
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

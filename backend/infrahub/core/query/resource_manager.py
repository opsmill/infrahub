from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Generator, Unpack

from infrahub.core import registry
from infrahub.core.constants import NULL_VALUE, InfrahubKind, RelationshipStatus
from infrahub.core.query import Query, QueryInitKwargs, QueryResult, QueryType
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreNumberPool
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class PoolRecordProvenance(StrEnum):
    """Whether the pool allocated a value or a user provided it."""

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

    provenance: PoolRecordProvenance
    """Whether the pool allocated the value the branch holds or a user provided it."""


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
        MATCH (pool:Node:%(ipaddress_pool)s { uuid: $pool_id })-[reservation:IS_RESERVED]->(allocated:BuiltinIPAddress)
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
        MATCH (pool:Node:%(ipaddress_pool)s { uuid: $pool_id })-[rel:IS_RESERVED]->(address:BuiltinIPAddress)
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
        MATCH (pool:Node:%(ipaddress_pool)s { uuid: $pool_id })
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
        ranges: list[list[int]],
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.ranges = ranges

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["node_attribute"] = self.pool.node_attribute.value
        self.params["ranges"] = self.ranges
        self.params["pool_id"] = self.pool.get_id()

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        query = """
        MATCH (pool:Node:%(number_pool_kind)s { uuid: $pool_id })-[ir:IS_RESERVED]->(a:Attribute {name: $node_attribute})
        MATCH (n:%(node)s)-[ha:HAS_ATTRIBUTE]->(a)-[hv:HAS_VALUE]->(av:AttributeValueIndexed)
        WHERE
            any(r IN $ranges WHERE av.value >= r[0] AND av.value <= r[1])
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

        # A record without a list predates the list and reads as allocated for every value it accounts for.
        self.return_labels = [
            "DISTINCT n.uuid as id",
            "hv.branch as branch",
            "av.value as value",
            "ir.identifier as identifier",
            "ir.allocated_values IS NOT NULL AND NOT toInteger(av.value) IN ir.allocated_values AS is_provided",
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
                provenance=PoolRecordProvenance.PROVIDED
                if result.get_as_type("is_provided", bool)
                else PoolRecordProvenance.ALLOCATED,
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
        """Return the value a single IS_RESERVED edge resolves to.

        Returns:
            The reserved integer value, or None if no live IS_RESERVED edge resolves to one.

        """
        result = self.get_result()
        if result is None:
            return None
        if result.get("value") in (None, NULL_VALUE):
            return None
        return result.get_as_type("value", return_type=int)

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


class NumberPoolGetTrackingPool(Query):
    """Find the number pool whose live IS_RESERVED edge points at an Attribute vertex."""

    name = "numberpool_get_tracking_pool"
    type = QueryType.READ

    def __init__(
        self,
        attribute_id: str,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.attribute_id = attribute_id

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["attribute_id"] = self.attribute_id
        self.params["at"] = self.at.to_string()

        query = """
        MATCH (attr:Attribute { uuid: $attribute_id })
        WITH attr
        LIMIT 1
        CALL (attr) {
            // --------
            // assumes IS_RESERVED is on the global branch
            // --------
            MATCH (pool:Node:%(number_pool)s)-[r:IS_RESERVED]->(attr)
            WHERE r.from <= $at AND (r.to IS NULL OR r.to > $at)
            ORDER BY r.from DESC, r.status ASC
            RETURN pool.uuid AS pool_id, r.status = "active" AS is_active
            LIMIT 1
        }
        WITH pool_id
        WHERE is_active = TRUE
        """ % {"number_pool": InfrahubKind.NUMBERPOOL}
        self.add_to_query(query)
        self.return_labels = ["pool_id"]

    def get_pool_id(self) -> str | None:
        """Return the id of the tracking pool, or None if no live IS_RESERVED edge points at the attribute."""
        result = self.get_result()
        if result:
            return result.get_as_type("pool_id", return_type=str)
        return None


class IPPoolChangeReserved(Query):
    """Point an IP pool's IS_RESERVED edges at a new identifier.

    Used when a node is converted to a different type and its id changes. An IP pool reserves the
    allocated `:Node` itself, so the IS_RESERVED edge keeps its target and only the identifier moves.
    """

    name = "ip_pool_change_reserved"
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
        MATCH (pool:%(ipaddress_pool)s|%(prefix_pool)s)-[r:IS_RESERVED]->(resource:Node)
        WHERE
            r.identifier = $existing_identifier
            AND
            %(branch_filter)s
        SET r.to = $at
        CREATE (pool)-[new_rel:IS_RESERVED $rel_prop]->(resource)
        """ % {
            "branch_filter": branch_filter,
            "ipaddress_pool": InfrahubKind.IPADDRESSPOOL,
            "prefix_pool": InfrahubKind.IPPREFIXPOOL,
        }
        self.add_to_query(query)
        self.return_labels = ["pool.uuid AS pool_id", "r", "new_rel"]


class NumberPoolChangeReserved(Query):
    """Move a number pool's reservations from a converted object onto the object that replaced it.

    The IS_RESERVED edges are moved from the `:Attribute` vertices of the old object to the
    `:Attribute` vertices of the replacement object. Handles multiple pools for different Attributes.
    The IS_RESERVED edge on the old attribute is left as it is: it stays open while any branch can
    still reach the old attribute and is closed once none can.
    """

    name = "number_pool_change_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        existing_node_id: str,
        new_node_id: str,
        existing_identifier: str,
        new_identifier: str,
        not_closed_before: Timestamp,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.existing_node_id = existing_node_id
        self.new_node_id = new_node_id
        self.existing_identifier = existing_identifier
        self.new_identifier = new_identifier
        self.not_closed_before = not_closed_before

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["existing_node_id"] = self.existing_node_id
        self.params["new_node_id"] = self.new_node_id
        self.params["new_identifier"] = self.new_identifier
        self.params["existing_identifier"] = self.existing_identifier
        self.params["not_closed_before"] = self.not_closed_before.to_string()
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id

        # What a pool tracks is itself branch-aware data: a pool can be repointed at another kind or
        # attribute, so both subqueries read it as of this branch and time.
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), variable_name="hv")
        self.params.update(branch_params)

        global_branch = registry.get_global_branch()
        self.params["rel_prop"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
            "identifier": self.new_identifier,
        }

        query = """
        // --------------
        // Anchored on the replaced object
        // --------------
        MATCH (:Node { uuid: $existing_node_id })-[:HAS_ATTRIBUTE]->(old_attr:Attribute)
        WITH DISTINCT old_attr
        MATCH (pool:%(number_pool)s)-[old_rel:IS_RESERVED]->(old_attr)
        // --------------
        // assumes the IS_RESERVED edge is on the global branch
        // --------------
        WHERE old_rel.identifier = $existing_identifier
          AND old_rel.status = "active"
          AND (old_rel.to IS NULL OR old_rel.to >= $not_closed_before)
        // --------------
        // Not closed here: object-delete and branch-delete retirement close it once no branch reaches it
        // --------------
        WITH DISTINCT pool, properties(old_rel) AS old_props
        // --------------
        // Each pool names the attribute it tracks, so read it rather than assuming one attribute.
        // --------------
        CALL (pool) {
            MATCH (pool)-[:HAS_ATTRIBUTE]->(:Attribute { name: "node_attribute" })-[hv:HAS_VALUE]->(av)
            WHERE %(branch_filter)s
            WITH av, hv
            ORDER BY hv.branch_level DESC, hv.from DESC
            LIMIT 1
            RETURN av.value AS tracked_attribute_name, hv.status = "active" AS is_active
        }
        WITH pool, old_props, tracked_attribute_name
        WHERE is_active = TRUE
        // --------------
        // And the kind it tracks, so a pool cannot follow the IS_RESERVED edge onto a kind it knows nothing about.
        // --------------
        CALL (pool) {
            MATCH (pool)-[:HAS_ATTRIBUTE]->(:Attribute { name: "node" })-[hv:HAS_VALUE]->(av)
            WHERE %(branch_filter)s
            WITH av, hv
            ORDER BY hv.branch_level DESC, hv.from DESC
            LIMIT 1
            RETURN av.value AS tracked_node_kind, hv.status = "active" AS is_active
        }
        WITH pool, old_props, tracked_attribute_name, tracked_node_kind
        WHERE is_active = TRUE
        MATCH (new_node:Node { uuid: $new_node_id })-[:HAS_ATTRIBUTE]->(new_attr:Attribute)
        WHERE new_attr.name = tracked_attribute_name
          AND tracked_node_kind IN labels(new_node)
        WITH DISTINCT pool, new_attr, old_props
        WHERE NOT EXISTS {
            MATCH (pool)-[mine:IS_RESERVED]->(new_attr)
            WHERE mine.status = "active" AND mine.to IS NULL
        }
        // ----------
        // Only one active IS_RESERVED edge for any attribute exists at a time
        // ----------
        OPTIONAL MATCH (holding_pool)-[live:IS_RESERVED]->(new_attr)
        WHERE live.status = "active" AND live.to IS NULL
        SET live.to = $at, live.to_user_id = $user_id
        %(stamp_holding_pool)s
        WITH DISTINCT pool, new_attr, old_props
        CREATE (pool)-[new_rel:IS_RESERVED]->(new_attr)
        SET new_rel = old_props
        SET new_rel += $rel_prop
        // --------------
        // unset the properties for closed edges
        // --------------
        REMOVE new_rel.to, new_rel.to_user_id
        %(stamp_pool)s
        """ % {
            "number_pool": InfrahubKind.NUMBERPOOL,
            "branch_filter": branch_filter,
            "stamp_holding_pool": stamp_vertex_metadata("holding_pool"),
            "stamp_pool": stamp_vertex_metadata("pool"),
        }
        self.add_to_query(query)
        self.return_labels = ["pool.uuid AS pool_id", "new_attr.uuid AS attribute_id", "new_rel"]


def reserved_values_query(
    pool_id: str, attribute_name: str, at: str, default_branch_name: str
) -> tuple[str, dict[str, Any]]:
    """Cypher fragment to find all Attributes reserved for a given NumberPool, with the parameters it reads.

    Finds every value some non-deleting branch holds on each reserved Attribute. A value counts when
    its HAS_VALUE edge is open now, or when a branch forked from the edge's branch while the edge was
    open and has written no edge of its own that hides the default-branch version.

    Final values are res (IS_RESERVED edge) and value (an active Attribute value).
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
        "attribute_name": attribute_name,
        "at": at,
        "default_branch_name": default_branch_name,
    }
    query = """
    // --------------
    // Read the branches once: the ones being deleted, and the fork window of every other user branch
    // --------------
    MATCH (branch:Branch)
    WITH collect(branch) AS branches
    WITH
        [b IN branches WHERE b.status = "DELETING" | b.name] AS deleting_branches,
        [b IN branches
            WHERE b.status <> "DELETING" AND NOT b.is_default AND NOT b.is_global
            | {name: b.name, origin_name: b.origin_branch, fork_at: b.branched_from}] AS branch_windows
    // --------------
    // Start with all the Attributes currently reserved for this pool
    // --------------
    MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })-[res:IS_RESERVED]->(attr:Attribute { name: $attribute_name })
    WHERE res.status = "active" AND res.from <= $at AND (res.to IS NULL OR res.to > $at)
    CALL (attr, deleting_branches, branch_windows) {
        // --------------
        // Every value edge open now, on any branch that is not being deleted
        // --------------
        MATCH (attr)-[hv:HAS_VALUE]->(av)
        WHERE hv.status = "active"
          AND hv.from <= $at AND (hv.to IS NULL OR hv.to > $at)
          AND NOT hv.branch IN deleting_branches
        RETURN av.value AS value
        UNION
        // --------------
        // For any edges closed on the default branch, check if they are still reachable
        // on other branches.
        // Start with closed edges on the default branch that user branches might still see as active.
        // --------------
        MATCH (attr)-[hv:HAS_VALUE {branch: $default_branch_name}]->(av)
        WHERE hv.status = "active"
        AND hv.to <= $at
        AND any(
            window IN branch_windows WHERE window.origin_name = hv.branch
            AND hv.from <= window.fork_at AND window.fork_at < hv.to
        )
        WITH hv, av, COLLECT {
            // --------------
            // Find any branches with edges that override the default branch HAS_VALUE edge.
            // Any value edge the branch wrote that is open now hides the origin's value: an active one
            // (the branch changed the value) or a deleted one (it removed the object or the attribute).
            // --------------
            MATCH (attr)-[hiding:HAS_VALUE]->()
            WHERE hiding.from <= $at AND (hiding.to IS NULL OR hiding.to > $at)
            RETURN hiding.branch AS branch_name
        } AS hiding_branches
        // --------------
        // If all the branches that this HAS_VALUE edge are visible on have overridden the value,
        // then leave it out b/c it is no longer active.
        // --------------
        WHERE any(window IN branch_windows WHERE window.origin_name = hv.branch
            AND hv.from <= window.fork_at AND window.fork_at < hv.to
            AND NOT window.name IN hiding_branches)
        RETURN av.value AS value
    }
    WITH DISTINCT res, value
    """ % {"number_pool": InfrahubKind.NUMBERPOOL}
    return query, params


class NumberPoolGetUsed(Query):
    """A pool is branch-agnostic, and so is the set of numbers it accounts for.

    The read carries no branch filter at all: the IS_RESERVED edge is global, and a value counts while any
    branch holds it.
    """

    name = "number_pool_get_used"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        ranges: list[list[int]],
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.ranges = ranges

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["ranges"] = self.ranges

        reserved_values, reserved_values_params = reserved_values_query(
            pool_id=self.pool.get_id(),
            attribute_name=self.pool.node_attribute.value,
            at=self.at.to_string(),
            default_branch_name=registry.default_branch,
        )
        self.params.update(reserved_values_params)

        query = """
        %(reserved_values)s
        WHERE any(r IN $ranges WHERE toInteger(value) >= r[0] AND toInteger(value) <= r[1])
        """ % {
            "reserved_values": reserved_values,
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

    The read carries no branch filter at all: the IS_RESERVED edge is global, and a value counts while any
    branch holds it.
    """

    name = "number_pool_get_free"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        min_value: int,
        max_value: int,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.min_value = min_value
        self.max_value = max_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["start_range"] = self.min_value
        self.params["end_range"] = self.max_value
        self.limit = 1  # Query only works at returning a single, free entry

        reserved_values, reserved_values_params = reserved_values_query(
            pool_id=self.pool.get_id(),
            attribute_name=self.pool.node_attribute.value,
            at=self.at.to_string(),
            default_branch_name=registry.default_branch,
        )
        self.params.update(reserved_values_params)

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
            "reserved_values": reserved_values,
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
        ranges: list[list[int]],
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.ranges = ranges

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["ranges"] = self.ranges

        # is_isolated=False mirrors the uniqueness validator: a value added to the origin branch after
        # this branch point still collides here.
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic, is_isolated=False
        )

        self.params.update(branch_params)
        self.params["attribute_name"] = self.pool.node_attribute.value

        # One plain range predicate per range lets the planner seek the value index; an any() over the
        # ranges cannot, and scans every attribute of that name instead.
        query = """
        UNWIND $ranges AS range_bounds
        MATCH (n:%(node)s)-[:HAS_ATTRIBUTE]->(attr:Attribute { name: $attribute_name })-[:HAS_VALUE]->(av:AttributeValueIndexed)
        WHERE av.value >= range_bounds[0] AND av.value <= range_bounds[1]
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
        WHERE is_active = True AND any(r IN $ranges WHERE value >= r[0] AND value <= r[1])
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

    Takes a write lock on the Attribute vertex, then keeps this pool's live IS_RESERVED edge unless the write
    allocates a number the record does not list yet. When no edge is kept, it ends every live IS_RESERVED edge
    on the attribute and creates this pool's record, whose `allocated_values` carries every number the pool
    allocated to the attribute so far plus the one allocated now, if any.

    The list is never changed in place: extending it closes the record and creates a new one, which keeps the
    history and stamps the pool like any other record change. The list is only ever tested for membership, so
    its order carries no meaning.
    """

    name = "numberpool_set_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        attribute_id: str,
        allocated_value: int | None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier
        self.attribute_id = attribute_id
        self.allocated_value = allocated_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["allocated_value"] = self.allocated_value
        self.params["attribute_id"] = self.attribute_id

        global_branch = registry.get_global_branch()
        self.params["rel_prop"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
            "from_user_id": self.user_id,
            "identifier": self.identifier,
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
        // Lock the Attribute vertex until the transaction ends, so a concurrent write to this attribute waits
        // and then reads the IS_RESERVED edges this one commits
        // ----------
        SET attr._number_pool_lock = TRUE
        REMOVE attr._number_pool_lock
        WITH pool, attr
        // ----------
        // Keep this pool's live IS_RESERVED edge unless the write allocates a number it does not list yet
        // ----------
        OPTIONAL MATCH (pool)-[own:IS_RESERVED]->(attr)
        WHERE own.status = "active"
          AND own.to IS NULL
        WITH pool, attr, own
        ORDER BY own.from DESC
        LIMIT 1
        WITH pool, attr,
            CASE
                WHEN own IS NULL THEN []
                WHEN $allocated_value IS NULL OR $allocated_value IN coalesce(own.allocated_values, []) THEN [own]
                ELSE []
            END AS kept_edges,
            CASE
                WHEN $allocated_value IS NULL THEN coalesce(own.allocated_values, [])
                ELSE coalesce(own.allocated_values, []) + [$allocated_value]
            END AS allocated_values
        // ----------
        // End every other live IS_RESERVED edge on the attribute, and stamp the pool that loses it
        // ----------
        CALL (attr, kept_edges) {
            MATCH (other_pool:Node:%(number_pool)s)-[live:IS_RESERVED]->(attr)
            WHERE live.status = "active"
              AND live.to IS NULL
              AND NOT live IN kept_edges
            SET live.to = $at, live.to_user_id = $user_id
            %(stamp_other_pool)s
        }
        // ----------
        // Create the expected IS_RESERVED edge unless one was kept, which is the only case the pool changes
        // ----------
        WITH pool, attr, kept_edges, allocated_values
        WHERE size(kept_edges) = 0
        CREATE (pool)-[rel:IS_RESERVED $rel_prop]->(attr)
        SET rel.allocated_values = allocated_values
        %(stamp_pool)s
        """ % {
            "number_pool": InfrahubKind.NUMBERPOOL,
            "stamp_other_pool": stamp_vertex_metadata("other_pool"),
            "stamp_pool": stamp_vertex_metadata("pool"),
        }

        self.add_to_query(query)
        self.return_labels = ["attr.uuid AS attribute_id", "rel"]


class NumberPoolReleaseReserved(Query):
    """End every live IS_RESERVED edge on an Attribute vertex, whichever number pool it comes from, leaving the value.

    The edge is closed in time because an IS_RESERVED edge lives on the global branch, where a removal on the
    same branch sets `to`.
    """

    name = "numberpool_release_reserved"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        attribute_id: str,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.attribute_id = attribute_id

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["attribute_id"] = self.attribute_id
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id

        query = """
        MATCH (attr:Attribute { uuid: $attribute_id })
        WITH attr
        LIMIT 1
        // ----------
        // Lock the Attribute vertex until the transaction ends, so writes to its IS_RESERVED edges run one at a time
        // ----------
        SET attr._number_pool_lock = TRUE
        REMOVE attr._number_pool_lock
        WITH attr
        MATCH (pool:Node:%(number_pool)s)-[live:IS_RESERVED]->(attr)
        WHERE live.status = "active"
          AND live.to IS NULL
        SET live.to = $at, live.to_user_id = $user_id
        %(stamp_pool)s
        """ % {"number_pool": InfrahubKind.NUMBERPOOL, "stamp_pool": stamp_vertex_metadata("pool")}

        self.add_to_query(query)


class NumberPoolReleaseAllReserved(Query):
    """End every live IS_RESERVED edge a number pool holds, leaving each attribute's value in place."""

    name = "numberpool_release_all_reserved"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        pool_id: str,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id

        query = """
        MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })-[live:IS_RESERVED]->(:Attribute)
        WHERE live.status = "active"
          AND live.to IS NULL
        SET live.to = $at, live.to_user_id = $user_id
        %(stamp_pool)s
        """ % {"number_pool": InfrahubKind.NUMBERPOOL, "stamp_pool": stamp_vertex_metadata("pool")}

        self.add_to_query(query)


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

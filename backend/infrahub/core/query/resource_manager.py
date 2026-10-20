from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generator, Unpack

from infrahub.core import registry
from infrahub.core.constants import (
    NULL_VALUE,
    InfrahubKind,
    PoolRecordProvenance,
    RelationshipStatus,
)
from infrahub.core.query import Query, QueryInitKwargs, QueryResult, QueryType
from infrahub.core.query.vertex_metadata import stamp_vertex_metadata
from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.protocols import CoreNumberPool
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.scope import Division, DivisionElementPath


@dataclass(frozen=True)
class TrackingPool:
    """The number pool whose live record covers an attribute, and what that record says about one value."""

    pool_id: str
    provenance: PoolRecordProvenance


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

    Reports every value a live branch holds for the given NumberPool along with its parent object ID,
    the holding branch, and reservation identifier, ordered by value, then branch, then the holding object's id. `branch_name`
    keeps the values held on that branch and `provenance` the values of that provenance. With a division, which may
    give a value for only some of the scope elements, only the values whose holding object is in the division on some
    live branch are reported.
    """

    name = "numberpool_get_allocated"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        ranges: list[list[int]],
        branch_name: str | None = None,
        provenance: PoolRecordProvenance | None = None,
        division: Division | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.ranges = ranges
        self.branch_name = branch_name
        self.provenance = provenance
        self.division = division

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["ranges"] = self.ranges

        division_filter = ""
        if self.division is not None:
            division_filter, division_params = division_filter_query(division=self.division)
            self.params.update(division_params)
        reserved_values, reserved_values_params = reserved_values_query(
            pool_id=self.pool.get_id(),
            attribute_name=self.pool.node_attribute.value,
            at=self.at.to_string(),
            default_branch_name=registry.default_branch,
            division_filter=division_filter,
        )
        self.params.update(reserved_values_params)

        query = """
        %(reserved_values)s
        WHERE any(r IN $ranges WHERE toInteger(value) >= r[0] AND toInteger(value) <= r[1])
        CALL (attr) {
            MATCH (node:%(node)s)-[:HAS_ATTRIBUTE]->(attr)
            RETURN node.uuid AS id
            LIMIT 1
        }
        """ % {"reserved_values": reserved_values, "node": self.pool.node.value}
        self.add_to_query(query)

        # The rows are made distinct before the filters so that the count query counts the rows returned.
        # A record without a list predates the list and reads as allocated for every value it accounts for.
        self.add_to_query(
            """
        WITH DISTINCT id, branch, value, res.identifier AS identifier,
            res.allocated_values IS NOT NULL AND NOT toInteger(value) IN res.allocated_values AS is_provided
        """
        )

        filters: list[str] = []
        if self.branch_name is not None:
            self.params["branch_name"] = self.branch_name
            filters.append("branch = $branch_name")
        if self.provenance is not None:
            self.params["is_provided"] = self.provenance == PoolRecordProvenance.PROVIDED
            filters.append("is_provided = $is_provided")
        if filters:
            self.add_to_query("WHERE " + " AND ".join(filters))

        self.return_labels = ["id", "branch", "value", "identifier", "is_provided"]
        self.order_by = ["value", "branch", "id"]

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

    Returns the values and identifiers for a given NumberPool's reservations on a given branch. Can
    optionally be filtered by identifier. With a division, only the reservations whose Attribute's Node is in
    the division on some live branch are returned.
    """

    name = "numberpool_get_reserved"
    type = QueryType.READ

    def __init__(
        self,
        pool_id: str,
        identifier: str | None = None,
        division: Division | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier
        self.division = division

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier
        self.params["at"] = self.at.to_string()

        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), branch_agnostic=self.branch_agnostic
        )
        self.params.update(branch_params)

        live_branches = ""
        branch_variables = ""
        division_filter = ""
        if self.division is not None:
            live_branches = LIVE_BRANCHES_QUERY
            branch_variables = ", deleting_branches, branch_windows"
            division_filter, division_params = division_filter_query(division=self.division)
            self.params.update(division_params)
            self.params["default_branch_name"] = registry.default_branch

        query = """
        %(live_branches)s
        MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })-[r_edge:IS_RESERVED]->(attr:Attribute)
        WHERE ($identifier IS NULL OR r_edge.identifier = $identifier)
        WITH DISTINCT pool, attr%(branch_variables)s
        %(division)s
        WITH pool, attr
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
            "division": division_filter,
            "live_branches": live_branches,
            "branch_variables": branch_variables,
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


LIVE_BRANCHES_QUERY = """
    // --------------
    // Read the branches once: the ones being deleted, and the fork window of every other user branch
    // --------------
    MATCH (branch:Branch)
    WITH collect(branch) AS branches
    WITH
        [b IN branches WHERE b.status = "DELETING" | b.name] AS deleting_branches,
        [b IN branches
            WHERE b.status <> "DELETING" AND NOT b.is_default AND NOT b.is_global
            | {name: b.name, origin_name: b.origin_branch, fork_at: b.branched_from}] AS branch_windows"""


def _live_on_some_branch(edge: str, hiding_pattern: str) -> str:
    """Return a Cypher predicate that is true when `edge` is visible now from at least one live branch.

    The edge is visible when it is open now on a branch not being deleted, or when it was closed on the default branch
    after a user branch forked and that branch has written no edge of its own matching `hiding_pattern` since.
    """
    return f"""{edge}.status = "active"
            AND {edge}.from <= $at
            AND NOT {edge}.branch IN deleting_branches
            AND (
                {edge}.to IS NULL OR {edge}.to > $at
                OR (
                    {edge}.branch = $default_branch_name
                    AND any(window IN branch_windows WHERE window.origin_name = {edge}.branch
                        AND {edge}.from <= window.fork_at AND window.fork_at < {edge}.to
                        AND NOT window.name IN COLLECT {{
                            MATCH {hiding_pattern}
                            WHERE hiding.from <= $at AND (hiding.to IS NULL OR hiding.to > $at)
                            RETURN hiding.branch
                        }})
                )
            )"""


_LIVE_EDGES = {
    "node_is_live": _live_on_some_branch(edge="ha", hiding_pattern="(node)-[hiding:HAS_ATTRIBUTE]->(attr)"),
    "value_is_live": _live_on_some_branch(edge="hv", hiding_pattern="(element_attr)-[hiding:HAS_VALUE]->()"),
    "peer_is_live": _live_on_some_branch(edge="r1", hiding_pattern="(node)-[hiding:IS_RELATED]-(rel)"),
    "direction_matches": """(
                        (element.direction = "outbound" AND startNode(r1) = node AND startNode(r2) = rel)
                        OR (element.direction = "inbound" AND endNode(r1) = node AND endNode(r2) = rel)
                        OR (element.direction = "bidirectional" AND endNode(r1) = rel AND endNode(r2) = rel)
                    )""",
}

# A schema migration can leave several Node vertices linked to one Attribute, each live on different branches.
DIVISION_FILTER_QUERY = (
    """
    // --------------
    // Keep the reserved Attribute when one of its Nodes is in the division on some live branch, each scope element
    // matching any value or peer that some live branch gives it
    // --------------
    WITH *
    WHERE EXISTS {
        MATCH (node:Node)-[ha:HAS_ATTRIBUTE]->(attr)
        WHERE %(node_is_live)s
        AND all(element IN $division_elements WHERE
            (
                element.direction IS NULL
                AND EXISTS {
                    MATCH (node)-[:HAS_ATTRIBUTE]->(element_attr:Attribute { name: element.name })-[hv:HAS_VALUE]->(av)
                    WHERE (av.value = element.value OR (element.value = "" AND av.value = $null_value))
                    AND %(value_is_live)s
                }
            )
            OR (
                element.direction IS NOT NULL
                AND EXISTS {
                    MATCH (node)-[r1:IS_RELATED]-(rel:Relationship { name: element.name })
                        -[r2:IS_RELATED]-(peer:Node { uuid: element.value })
                    WHERE %(direction_matches)s
                    AND r2.status = "active"
                    AND %(peer_is_live)s
                }
            )
        )
    }
"""
    % _LIVE_EDGES
)


def division_filter_query(division: Division) -> tuple[str, dict[str, Any]]:
    """Return the Cypher that keeps the reserved `attr` whose Node is in `division` on any live branch, with its parameters.

    A Node counts in every division it occupies on some branch, each scope element checked on its own, so a number is
    never handed out twice in one division whatever branches the two Nodes are on. The fragment reads the
    `deleting_branches`, `branch_windows`, `$at` and `$default_branch_name` that the enclosing query provides.
    """
    return DIVISION_FILTER_QUERY, {
        "division_elements": [
            {
                "name": element.name,
                "direction": element.relationship_direction.value
                if element.relationship_direction is not None
                else None,
                "value": value,
            }
            for element, value in zip(division.elements, division.values, strict=True)
        ],
        "null_value": NULL_VALUE,
    }


LIVE_DIVISIONS_QUERY = """
    // --------------
    // Every division a Node of the reserved Attribute occupies on some live branch, each scope element taking any
    // value or peer that some live branch gives it
    // --------------
    CALL (attr, deleting_branches, branch_windows) {
        MATCH (node:Node)-[ha:HAS_ATTRIBUTE]->(attr)
        WHERE %(node_is_live)s
        %(elements)s
        RETURN DISTINCT %(division_values)s AS division_values
    }"""

LIVE_ATTRIBUTE_ELEMENT_QUERY = """
        CALL (node, deleting_branches, branch_windows) {
            WITH node, $division_elements[%(idx)s] AS element
            MATCH (node)-[:HAS_ATTRIBUTE]->(element_attr:Attribute { name: element.name })-[hv:HAS_VALUE]->(av)
            WHERE %(value_is_live)s
            RETURN DISTINCT CASE WHEN av.value = $null_value THEN "" ELSE av.value END AS division_value_%(idx)s
        }"""

# A schema migration can link another vertex of the same Node to the Relationship vertex, which is not a peer.
LIVE_RELATIONSHIP_ELEMENT_QUERY = """
        CALL (node, deleting_branches, branch_windows) {
            WITH node, $division_elements[%(idx)s] AS element
            MATCH (node)-[r1:IS_RELATED]-(rel:Relationship { name: element.name })-[r2:IS_RELATED]-(peer:Node)
            WHERE %(direction_matches)s
            AND peer.uuid <> node.uuid
            AND r2.status = "active"
            AND %(peer_is_live)s
            RETURN DISTINCT peer.uuid AS division_value_%(idx)s
        }"""


def live_divisions_query(elements: Sequence[DivisionElementPath]) -> tuple[str, dict[str, Any]]:
    """Return the Cypher that gives each reserved `attr` one row per division its Node occupies on any live branch.

    A Node with no live value for an element of the scope occupies no division. The fragment reads the
    `deleting_branches`, `branch_windows`, `$at` and `$default_branch_name` that the enclosing query provides.
    """
    element_queries = [
        (LIVE_ATTRIBUTE_ELEMENT_QUERY if element.relationship_direction is None else LIVE_RELATIONSHIP_ELEMENT_QUERY)
        % {**_LIVE_EDGES, "idx": idx}
        for idx, element in enumerate(elements)
    ]
    query = LIVE_DIVISIONS_QUERY % {
        "node_is_live": _LIVE_EDGES["node_is_live"],
        "elements": "".join(element_queries),
        "division_values": "[%s]" % ", ".join(f"division_value_{idx}" for idx in range(len(elements))),
    }
    return query, {
        "division_elements": [
            {
                "name": element.name,
                "direction": element.relationship_direction.value
                if element.relationship_direction is not None
                else None,
            }
            for element in elements
        ],
        "null_value": NULL_VALUE,
    }


@dataclass(frozen=True)
class NumberPoolDivisionResult:
    """How many numbers one division of a scoped pool holds."""

    values: tuple[str | int | float | bool, ...]
    """The division's value for each scope element, in scope order."""

    used: int
    """Numbers in use on any branch; a number used on several branches counts once."""

    used_default_branch: int
    """Numbers in use on the default branch."""

    @property
    def used_branches(self) -> int:
        """Numbers in use only on other branches than the default branch."""
        return self.used - self.used_default_branch


class NumberPoolGetDivisions(Query):
    """Count the numbers each division of a scoped pool holds, for every division that holds at least one.

    A number counts while any branch holds it, as for the pool's figures, and in every division its holding object
    occupies on any live branch. `elements` says where a Node keeps each scope element, in scope order.
    """

    name = "numberpool_get_divisions"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        ranges: list[list[int]],
        elements: Sequence[DivisionElementPath],
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.ranges = ranges
        self.elements = elements

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
        divisions_query, divisions_params = live_divisions_query(elements=self.elements)
        self.params.update(divisions_params)

        query = """
        %(reserved_values)s
        WHERE any(r IN $ranges WHERE toInteger(value) >= r[0] AND toInteger(value) <= r[1])
        WITH DISTINCT attr, value, branch, deleting_branches, branch_windows
        %(divisions)s
        WITH division_values, value, collect(DISTINCT branch) AS branches
        WITH division_values, value, $default_branch_name IN branches AS on_default_branch
        """ % {
            "reserved_values": reserved_values,
            "divisions": divisions_query,
        }
        self.add_to_query(query)

        self.return_labels = [
            "division_values",
            "count(value) AS used",
            "sum(CASE WHEN on_default_branch THEN 1 ELSE 0 END) AS used_default_branch",
        ]
        # The rows are read in pages when no limit is given, so each page needs one stable order.
        self.order_by = ["division_values"]

    def get_data(self) -> list[NumberPoolDivisionResult]:
        return [
            NumberPoolDivisionResult(
                values=tuple(result.get_as_type("division_values", list)),
                used=result.get_as_type("used", int),
                used_default_branch=result.get_as_type("used_default_branch", int),
            )
            for result in self.get_results()
        ]


def reserved_values_query(
    pool_id: str,
    attribute_name: str,
    at: str,
    default_branch_name: str,
    division_filter: str = "",
) -> tuple[str, dict[str, Any]]:
    """Cypher fragment to find all Attributes reserved for a given NumberPool, with the parameters it reads.

    Finds every value some non-deleting branch holds on each reserved Attribute, with the branch that holds it. A
    value counts on the edge's branch when its HAS_VALUE edge is open now, and on each branch that forked from the
    edge's branch while the edge was open and has written no edge of its own that hides the default-branch version.

    `division_filter` is inserted after the reserved Attributes are matched, to keep only those of a division.

    Final values are res (IS_RESERVED edge), attr (the reserved Attribute), value (an active Attribute value),
    branch (a branch holding the value), deleting_branches and branch_windows.
    """
    params: dict[str, Any] = {
        "pool_id": pool_id,
        "attribute_name": attribute_name,
        "at": at,
        "default_branch_name": default_branch_name,
    }
    query = """
%(live_branches)s
    // --------------
    // Start with all the Attributes currently reserved for this pool
    // --------------
    MATCH (pool:Node:%(number_pool)s { uuid: $pool_id })-[res:IS_RESERVED]->(attr:Attribute { name: $attribute_name })
    WHERE res.status = "active" AND res.from <= $at AND (res.to IS NULL OR res.to > $at)
%(division)s    CALL (attr, deleting_branches, branch_windows) {
        // --------------
        // Every value edge open now, on any branch that is not being deleted
        // --------------
        MATCH (attr)-[hv:HAS_VALUE]->(av)
        WHERE hv.status = "active"
          AND hv.from <= $at AND (hv.to IS NULL OR hv.to > $at)
          AND NOT hv.branch IN deleting_branches
        RETURN av.value AS value, hv.branch AS branch
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
        WITH hv, av, branch_windows, COLLECT {
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
        // The value is held by each branch this HAS_VALUE edge is visible on that has not overridden it
        // --------------
        UNWIND [window IN branch_windows WHERE window.origin_name = hv.branch
            AND hv.from <= window.fork_at AND window.fork_at < hv.to
            AND NOT window.name IN hiding_branches | window.name] AS branch
        RETURN av.value AS value, branch
    }
    WITH DISTINCT res, attr, value, branch, deleting_branches, branch_windows
    """ % {"number_pool": InfrahubKind.NUMBERPOOL, "division": division_filter, "live_branches": LIVE_BRANCHES_QUERY}
    return query, params


class NumberPoolGetUsed(Query):
    """A pool is branch-agnostic, and so is the set of numbers it accounts for.

    The read of the IS_RESERVED edges carries no branch filter: the edge is global, and a value counts while any
    branch holds it. For a division, a value counts when its Node is in the division on any branch.
    """

    name = "number_pool_get_used"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        ranges: list[list[int]],
        division: Division | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.ranges = ranges
        self.division = division

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["ranges"] = self.ranges

        division_filter = ""
        if self.division is not None:
            division_filter, division_params = division_filter_query(division=self.division)
            self.params.update(division_params)
        reserved_values, reserved_values_params = reserved_values_query(
            pool_id=self.pool.get_id(),
            attribute_name=self.pool.node_attribute.value,
            at=self.at.to_string(),
            default_branch_name=registry.default_branch,
            division_filter=division_filter,
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

    The read of the IS_RESERVED edges carries no branch filter: the edge is global, and a value counts while any
    branch holds it. For a division, a value counts when its Node is in the division on any branch.
    """

    name = "number_pool_get_free"
    type = QueryType.READ

    def __init__(
        self,
        pool: CoreNumberPool,
        min_value: int,
        max_value: int,
        division: Division | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool = pool
        self.min_value = min_value
        self.max_value = max_value
        self.division = division

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["start_range"] = self.min_value
        self.params["end_range"] = self.max_value
        self.limit = 1  # Query only works at returning a single, free entry

        division_filter = ""
        if self.division is not None:
            division_filter, division_params = division_filter_query(division=self.division)
            self.params.update(division_params)
        reserved_values, reserved_values_params = reserved_values_query(
            pool_id=self.pool.get_id(),
            attribute_name=self.pool.node_attribute.value,
            at=self.at.to_string(),
            default_branch_name=registry.default_branch,
            division_filter=division_filter,
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

    Takes a write lock on the Attribute vertex and then on the pool's vertex, then keeps this pool's live
    IS_RESERVED edge unless the write allocates a number the record does not list yet. When no edge is kept, it
    ends every live IS_RESERVED edge on the attribute and creates this pool's record, whose `allocated_values`
    carries every number the pool allocated to the attribute so far plus the one allocated now, if any.

    The list is never changed in place: extending it closes the record and creates a new one, which keeps the
    history and stamps the pool like any other record change. The list is only ever tested for membership, so
    its order carries no meaning.

    The row returned says whether `held_value`, the number the attribute holds after the write, is one the
    live record lists as allocated; `held_value` defaults to the number allocated now.
    """

    name = "numberpool_set_reserved"
    type = QueryType.WRITE

    def __init__(
        self,
        pool_id: str,
        identifier: str,
        attribute_id: str,
        allocated_value: int | None,
        held_value: int | None = None,
        **kwargs: Unpack[QueryInitKwargs],
    ) -> None:
        self.pool_id = pool_id
        self.identifier = identifier
        self.attribute_id = attribute_id
        self.allocated_value = allocated_value
        self.held_value = held_value

        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["pool_id"] = self.pool_id
        self.params["identifier"] = self.identifier
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id
        self.params["allocated_value"] = self.allocated_value
        self.params["held_value"] = self.held_value if self.held_value is not None else self.allocated_value
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
        // Lock the Attribute vertex, so a concurrent write waits to read the new IS_RESERVED edge
        // ----------
        SET attr._number_pool_lock = TRUE
        REMOVE attr._number_pool_lock
        // ----------
        // Lock the NumberPool vertex, so concurrent writes do not deadlock adding IS_RESERVED
        // ----------
        SET pool._number_pool_lock = TRUE
        REMOVE pool._number_pool_lock
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
        WITH pool, attr, own,
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
        WITH pool, attr, own, kept_edges, allocated_values
        CALL (pool, attr, kept_edges, allocated_values) {
            WITH *
            WHERE size(kept_edges) = 0
            CREATE (pool)-[rel:IS_RESERVED $rel_prop]->(attr)
            SET rel.allocated_values = allocated_values
            %(stamp_pool)s
        }
        // ----------
        // Report whether the number the attribute holds is one the live record lists as allocated
        // ----------
        WITH CASE WHEN size(kept_edges) = 0 THEN allocated_values ELSE own.allocated_values END AS live_allocated_values
        WITH live_allocated_values IS NOT NULL
            AND NOT coalesce($held_value IN live_allocated_values, FALSE) AS is_provided
        """ % {
            "number_pool": InfrahubKind.NUMBERPOOL,
            "stamp_other_pool": stamp_vertex_metadata("other_pool"),
            "stamp_pool": stamp_vertex_metadata("pool"),
        }

        self.add_to_query(query)
        self.return_labels = ["is_provided"]

    def get_provenance(self) -> PoolRecordProvenance:
        """What the live record says about the number the attribute holds after the write.

        Raises:
            InitializationError: When the write matched no pool and attribute, so no record was written.

        """
        result = self.get_result()
        if result is None:
            raise InitializationError(
                f"No record was written for attribute {self.attribute_id} and pool {self.pool_id}"
            )
        if result.get_as_type("is_provided", return_type=bool):
            return PoolRecordProvenance.PROVIDED
        return PoolRecordProvenance.ALLOCATED


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

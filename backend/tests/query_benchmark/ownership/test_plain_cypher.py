"""Measures of plain Cypher reads on the owner storage, with no product read query in the path.

The reads are for the default branch: an edge that passes the time filter and is active is then the latest edge.
"""

import os
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from itertools import batched
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, RelationshipKind
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
from infrahub.core.graph.index import rel_indexes
from infrahub.core.ownership.constants import MAX_INHERITANCE_DEPTH, NO_OWNER_VERTEX_UUID
from infrahub.core.ownership.models import NODE_HOLDER, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.neo4j import IndexRelNeo4j
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.test_app import TestInfrahubApp
from tests.query_benchmark.ownership.conftest import (
    DEVICE_KIND,
    INTERFACE_KIND,
    LOCATION_LEVELS,
    LOCATIONS_PER_PARENT,
    NB_DEVICES,
    NB_INTERFACES_PER_DEVICE,
    ReferenceDataSet,
)

LOCATION_DEPTH = len(LOCATION_LEVELS)
LOCATION_KINDS = [f"Bench{level}" for level in LOCATION_LEVELS]
NB_WARMUP_RUNS = 1
NB_MEASURED_RUNS = 7
NB_MUTATION_WARMUP_RUNS = 3
NB_MUTATION_RUNS = 200
# A generator writes each node with one upsert, so this is the number of nodes of the generator run.
NB_GENERATOR_NODES = int(os.environ.get("INFRAHUB_OWNERSHIP_BENCHMARK_GENERATOR_NODES", "10000"))
PAGE_SIZE = 50
NB_DEVICES_OF_A_PAGE = -(-PAGE_SIZE // NB_INTERFACES_PER_DEVICE)
WRITE_BATCH_SIZE = 5000

NB_DEVICE_GROUPS = 40
SECOND_DEVICE_GROUP = 40
LOCATION_OWNERS = {
    (3, 0): [41],
    (1, 0): [42],
    **{(LOCATION_DEPTH, 20 + offset): [44 + offset] for offset in range(6)},
}
"""Owner groups of a location, by level (1 is the top) and by index in the level."""
INTERFACE_GROUP = 43
INTERFACE_STATES: dict[int, list[int]] = {0: [INTERFACE_GROUP], 1: []}
"""Own owner groups of two ports, on one device in 50."""
FIRST_DEVICE_WITH_INTERFACE_STATES = 2
NEW_GROUP = 49

NB_BRANCH_CHANGES = 500
NB_OWNER_SETS = 1000
NB_OWNER_SETS_OF_ONE_NODE = 20
NO_OWNER_PORTS = [f"eth{port}" for port in range(40, 48)]
DIFF_BRANCH = "owner-diff"
INTERFACES_IDENTIFIER = "benchdevice__interfaces"

UPDATE = """
    mutation($id: String!, $description: String!) {
        BenchInterfaceUpdate(data: { id: $id, description: { value: $description } }) { ok }
    }
"""
UPSERT = """
    mutation($name: String!, $device: String!, $description: String!) {
        BenchInterfaceUpsert(
            data: { name: { value: $name }, device: { id: $device }, description: { value: $description } }
        ) { ok object { id } }
    }
"""


def device_state(device: int) -> list[int] | None:
    """Return the own owner groups of a device, an empty list for "no owner", or None when it inherits."""
    if device % 4 == 0:
        return [(device // 4) % NB_DEVICE_GROUPS] + ([SECOND_DEVICE_GROUP] if device % 8 == 0 else [])
    if device % 100 == 1:
        return []
    return None


def device_owners(device: int, nb_leaf_locations: int) -> tuple[list[int], int]:
    """Return the owner groups that apply to a device, and the number of parents up to the node that holds them."""
    state = device_state(device)
    if state is not None:
        return state, 0
    leaf = device % nb_leaf_locations
    for depth in range(1, LOCATION_DEPTH + 1):
        level = LOCATION_DEPTH + 1 - depth
        owners = LOCATION_OWNERS.get((level, leaf // LOCATIONS_PER_PARENT ** (depth - 1)))
        if owners is not None:
            return owners, depth
    return [], LOCATION_DEPTH


def has_interface_states(device: int) -> bool:
    return device % 50 == FIRST_DEVICE_WITH_INTERFACE_STATES


def interface_state(device: int, port: int) -> list[int] | None:
    return INTERFACE_STATES.get(port) if has_interface_states(device) else None


def interface_owners(device: int, port: int, nb_leaf_locations: int) -> list[int]:
    state = interface_state(device, port)
    return state if state is not None else device_owners(device, nb_leaf_locations)[0]


@dataclass(frozen=True)
class OwnedDataSet:
    data_set: ReferenceDataSet
    branch: Branch
    parents: dict[str, dict[str, str]]
    """For each kind, the relationship that passes owners down."""

    @property
    def nb_leaf_locations(self) -> int:
        return len(self.data_set.location_ids[LOCATION_LEVELS[-1]])

    def params(self, kinds: list[str] | None = None, **extra: object) -> dict[str, Any]:
        """Return the parameters of a read now. `kinds` are the kinds that a walk down can reach."""
        _, params = self.branch.get_query_filter_path(at=Timestamp())
        identifiers = [self.parents[kind]["identifier"] for kind in kinds or []]
        return {**params, "parents": self.parents, "kinds": kinds, "identifiers": identifiers, **extra}

    def expected_interfaces(self) -> tuple[dict[int, int], int]:
        """Return the number of interfaces that each group owns, and the number of interfaces with an owner."""
        by_group: dict[int, int] = dict.fromkeys(range(len(self.data_set.group_ids)), 0)
        nb_owned = 0
        for device in range(NB_DEVICES):
            for port in range(NB_INTERFACES_PER_DEVICE):
                owners = interface_owners(device, port, self.nb_leaf_locations)
                nb_owned += bool(owners)
                for group in owners:
                    by_group[group] += 1
        return by_group, nb_owned

    def devices(self, depth: int, owned: bool, count: int) -> list[int]:
        """Return devices that inherit, whose holder is `depth` parents above them, with or without owners."""
        found = [
            device
            for device in range(NB_DEVICES)
            if not has_interface_states(device)
            and device_state(device) is None
            and device_owners(device, self.nb_leaf_locations)[1] == depth
            and bool(device_owners(device, self.nb_leaf_locations)[0]) is owned
        ]
        return found[:count]


def _parent_relationships(schema_branch: SchemaBranch) -> dict[str, dict[str, str]]:
    parents: dict[str, dict[str, str]] = {}
    for name in schema_branch.node_names:
        schema = schema_branch.get_node(name=name, duplicate=False)
        relationship = next((rel for rel in schema.relationships if rel.kind == RelationshipKind.PARENT), None)
        if relationship is None:
            relationship = next(
                (
                    rel
                    for rel in schema.relationships
                    if rel.kind == RelationshipKind.HIERARCHY
                    and rel.identifier == PARENT_CHILD_IDENTIFIER
                    and rel.name == "parent"
                ),
                None,
            )
        if relationship is not None and relationship.identifier:
            parents[name] = {"identifier": relationship.identifier, "direction": relationship.direction.value}
    return parents


def _active(branch: Branch, variable: str) -> str:
    branch_filter, _ = branch.get_query_filter_path(variable_name=variable)
    return f'{branch_filter} AND {variable}.status = "active"'


def _alive(branch: Branch, node: str) -> str:
    return f"EXISTS {{ ({node})-[alive:IS_PART_OF]->(:Root) WHERE {_active(branch, 'alive')} }}"


def _own_state(branch: Branch, node: str) -> str:
    return f"EXISTS {{ ({node})-[own:HAS_OWNER|HAS_NO_OWNER]->() WHERE {_active(branch, 'own')} }}"


def _parent_step(branch: Branch, down: bool = False) -> str:
    """Return the pattern of one step between a child `c` that inherits and its parent `p`.

    A step down only follows the relationships of `$identifiers` to the kinds of `$kinds`, which are the ones on the
    way to the kind that the query lists.
    """
    pattern = "(c:Node)-[r1:IS_RELATED]-(rl:Relationship)-[r2:IS_RELATED]-(p:Node)"
    if down:
        pattern = "(p:Node)-[r2:IS_RELATED]-(rl:Relationship)-[r1:IS_RELATED]-(c:Node)"
    return f"""{pattern}
        WHERE {"rl.name IN $identifiers AND c.kind IN $kinds AND " if down else ""}rl.name = $parents[c.kind].identifier
        AND c <> p
        AND {_active(branch, "r1")} AND {_active(branch, "r2")}
        AND (
            ($parents[c.kind].direction = "bidirectional" AND startNode(r1) = c AND startNode(r2) = p)
            OR ($parents[c.kind].direction = "outbound" AND startNode(r1) = c AND startNode(r2) = rl)
            OR ($parents[c.kind].direction = "inbound" AND startNode(r1) = rl AND startNode(r2) = p)
        )
        AND NOT {_own_state(branch, "c")}"""


def _applying_owners_query(branch: Branch) -> str:
    """Walk up from each node to the first node that has its own owner state."""
    return f"""
UNWIND $node_ids AS node_id
MATCH (n:Node {{uuid: node_id}})
CALL (n) {{
    MATCH (n) (
        {_parent_step(branch)}
    ){{0,{MAX_INHERITANCE_DEPTH}}} (holder:Node)
    WHERE {_own_state(branch, "holder")}
    RETURN holder, size(r1) AS depth
    LIMIT 1
}}
OPTIONAL MATCH (holder)-[held:HAS_OWNER]->(owner:Node)
WHERE {_active(branch, "held")} AND {_alive(branch, "owner")}
RETURN node_id, holder.uuid AS holder_id, depth, collect(owner.uuid) AS owner_ids
"""


def _nodes_of_owners(branch: Branch, label: str, any_owner: bool = False) -> str:
    """Start from the owners, then go down from each node that holds them to the nodes of one kind that inherit."""
    return f"""
MATCH (owner:Node)<-[held:HAS_OWNER]-(h:Node)
WHERE {"" if any_owner else "owner.uuid IN $owner_ids AND "}{_active(branch, "held")} AND {_alive(branch, "owner")}
WITH DISTINCT h
MATCH (h) (
        {_parent_step(branch, down=True)}
){{0,{MAX_INHERITANCE_DEPTH}}} (n:{label})
WHERE {_alive(branch, "n")}
"""


def _nodes_without_owner_walk_up(branch: Branch, label: str) -> str:
    return f"""
MATCH (n:{label})
WHERE {_alive(branch, "n")}
AND NOT EXISTS {{
    MATCH (n) (
        {_parent_step(branch)}
    ){{0,{MAX_INHERITANCE_DEPTH}}} (holder:Node)-[held:HAS_OWNER]->(owner:Node)
    WHERE {_active(branch, "held")} AND {_alive(branch, "owner")}
}}
"""


def _nodes_without_owner_from_owners(branch: Branch, label: str) -> str:
    return f"""
{_nodes_of_owners(branch, label, any_owner=True)}
WITH collect(DISTINCT n) AS owned
MATCH (n:{label})
WHERE NOT n IN owned AND {_alive(branch, "n")}
"""


def _nodes_of_owners_walk_up(branch: Branch, label: str) -> str:
    return f"""
MATCH (n:{label})
WHERE {_alive(branch, "n")}
AND EXISTS {{
    MATCH (n) (
        {_parent_step(branch)}
    ){{0,{MAX_INHERITANCE_DEPTH}}} (holder:Node)-[held:HAS_OWNER]->(owner:Node)
    WHERE owner.uuid IN $owner_ids AND {_active(branch, "held")} AND {_alive(branch, "owner")}
}}
"""


COUNT = "RETURN count(DISTINCT n) AS count"
PAGE = f"WITH DISTINCT n ORDER BY n.uuid LIMIT {PAGE_SIZE} RETURN collect(n.uuid) AS page"

INTERFACE_IDS = f"""
UNWIND $device_ids AS device_id
MATCH (:Node {{uuid: device_id}})-[:IS_RELATED]->(:Relationship {{name: "{INTERFACES_IDENTIFIER}"}})
    <-[:IS_RELATED]-(i:Node)
MATCH (i)-[:HAS_ATTRIBUTE]->(:Attribute {{name: "name"}})-[:HAS_VALUE]->(v:AttributeValue)
WHERE $names IS NULL OR v.value IN $names
RETURN device_id, v.value AS name, i.uuid AS interface_id
"""

EDGE_PROPERTIES = '{branch: $branch, branch_level: $branch_level, status: "active", from: $at}'
SET_OWNERS = f"""
UNWIND $rows AS row
MATCH (n:Node {{uuid: row[0]}})
MATCH (owner:Node {{uuid: row[1]}})
CREATE (n)-[:HAS_OWNER {EDGE_PROPERTIES}]->(owner)
"""
SET_NO_OWNER = f"""
MERGE (no_owner:NoOwner {{uuid: $no_owner_uuid}})
WITH no_owner
UNWIND $rows AS node_id
MATCH (n:Node {{uuid: node_id}})
CREATE (n)-[:HAS_NO_OWNER {EDGE_PROPERTIES}]->(no_owner)
"""
SET_FIELD_OWNERS = f"""
UNWIND $rows AS row
MATCH (n:Node {{uuid: row[0]}})
MATCH (owner:Node {{uuid: row[2]}})
CREATE (n)-[:HAS_OWNER_SET {EDGE_PROPERTIES}]->(s:OwnerSet {{identifier: row[1], direction: "bidirectional"}})
CREATE (s)-[:HAS_OWNER {EDGE_PROPERTIES}]->(owner)
"""
OWNER_SET_LOOKUP = """
MATCH (n:Node {uuid: $node_id})-[r:HAS_OWNER_SET]->(s:OwnerSet)
WHERE s.identifier = $identifier AND s.direction = "bidirectional" AND %(active)s
RETURN elementId(s) AS owner_set
"""

DIFF_EDGE_FILTER = "r.branch = $branch AND $from_time <= r.from < $to_time"
DIFF_HOLDERS = {
    "node": "(n:Node)",
    "attribute": "(n:Node)-[:HAS_ATTRIBUTE]->(:Attribute)",
    "owner set": "(n:Node)-[:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(:OwnerSet)",
}


def _diff_query(hinted_edge_types: list[str]) -> str:
    """List the nodes whose owner edges changed on a branch, with one pattern for each edge type."""
    parts = []
    for holder, pattern in DIFF_HOLDERS.items():
        for edge_type in ("HAS_OWNER", "HAS_NO_OWNER"):
            hint = f"USING INDEX r:{edge_type}(branch)" if edge_type in hinted_edge_types else ""
            parts.append(
                f"MATCH {pattern}-[r:{edge_type}]->() {hint} WHERE {DIFF_EDGE_FILTER} "
                f'RETURN n.uuid AS node_id, "{holder}" AS holder'
            )
    return "CALL () {\n" + "\nUNION\n".join(parts) + "\n}\nRETURN node_id, holder"


def _edge_params(branch: Branch) -> dict[str, Any]:
    return {
        "branch": branch.name,
        "branch_level": branch.hierarchy_level,
        "at": Timestamp().to_string(),
        "no_owner_uuid": NO_OWNER_VERTEX_UUID,
    }


async def _write(db: InfrahubDatabase, query: str, rows: list[Any], params: dict[str, Any]) -> None:
    for chunk in batched(rows, WRITE_BATCH_SIZE):
        await db.execute_query(query=query, params={**params, "rows": list(chunk)})


async def _interface_ids(
    db: InfrahubDatabase, device_ids: list[str], names: list[str] | None = None
) -> dict[tuple[str, str], str]:
    """Return the ID of each interface, by the ID of its device and by its name."""
    interface_ids: dict[tuple[str, str], str] = {}
    for chunk in batched(device_ids, WRITE_BATCH_SIZE):
        rows = await db.execute_query(query=INTERFACE_IDS, params={"device_ids": list(chunk), "names": names})
        interface_ids.update({(row["device_id"], row["name"]): row["interface_id"] for row in rows})
    return interface_ids


async def _measure(
    db: InfrahubDatabase, query: str, params: dict[str, Any], runs: int = NB_MEASURED_RUNS, warmup: int = NB_WARMUP_RUNS
) -> tuple[list[float], list[Any]]:
    """Return the durations in milliseconds of the measured runs, and the rows of the last run."""
    durations: list[float] = []
    rows: list[Any] = []
    for _ in range(warmup + runs):
        start = time.perf_counter()
        rows = await db.execute_query(query=query, params=params)
        durations.append((time.perf_counter() - start) * 1000)
    return durations[warmup:], rows


async def _timed(db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]) -> float:
    """Return the duration in milliseconds of one GraphQL operation that runs in the test process."""
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    start = time.perf_counter()
    result = await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    duration = (time.perf_counter() - start) * 1000
    assert result.errors is None
    assert result.data
    return duration


def _sum_db_hits(plan: dict[str, Any]) -> int:
    return plan.get("dbHits", 0) + sum(_sum_db_hits(child) for child in plan.get("children", []))


async def _db_hits(db: InfrahubDatabase, query: str, params: dict[str, Any]) -> int:
    _, metadata = await db.execute_query_with_metadata(query="PROFILE\n" + query, params=params)
    return _sum_db_hits(metadata["profile"])


def _stats(values: list[float]) -> str:
    return f"{statistics.median(values):.1f} | {min(values):.1f} | {max(values):.1f}"


def _report(title: str, header: str, rows: list[str]) -> None:
    print(
        f"\n{title}. Data set: {NB_DEVICES} devices, {NB_DEVICES * NB_INTERFACES_PER_DEVICE} interfaces."
        f"\n| {header} |\n|{'---|' * (header.count('|') + 1)}"
    )
    for row in rows:
        print(f"| {row} |")


async def _applying_owners(
    db: InfrahubDatabase, owned: OwnedDataSet, node_ids: list[str]
) -> dict[str, tuple[str, int, tuple[str, ...]]]:
    """Return the holder, the number of parents up to it and the live owners, for each node that has a holder."""
    rows = await db.execute_query(query=_applying_owners_query(owned.branch), params=owned.params(node_ids=node_ids))
    return {row["node_id"]: (row["holder_id"], row["depth"], tuple(sorted(row["owner_ids"]))) for row in rows}


@pytest.fixture(scope="class")
async def owned_data_set(
    db: InfrahubDatabase, default_branch: Branch, reference_data_set: ReferenceDataSet
) -> OwnedDataSet:
    data_set = reference_data_set
    groups = data_set.group_ids
    params = _edge_params(branch=default_branch)

    owner_rows: list[tuple[str, str]] = []
    no_owner_rows: list[str] = []
    for (level, index), owners in LOCATION_OWNERS.items():
        owner_rows.extend((data_set.location_ids[LOCATION_LEVELS[level - 1]][index], groups[group]) for group in owners)
    special_devices: list[str] = []
    for device, device_id in enumerate(data_set.device_ids):
        state = device_state(device)
        if state == []:
            no_owner_rows.append(device_id)
        owner_rows.extend((device_id, groups[group]) for group in state or [])
        if has_interface_states(device):
            special_devices.append(device_id)
    special_interfaces = await _interface_ids(db=db, device_ids=special_devices, names=["eth0", "eth1"])
    for (_, name), interface_id in special_interfaces.items():
        if name == "eth0":
            owner_rows.append((interface_id, groups[INTERFACE_GROUP]))
        else:
            no_owner_rows.append(interface_id)

    await _write(db=db, query=SET_OWNERS, rows=owner_rows, params=params)
    await _write(db=db, query=SET_NO_OWNER, rows=no_owner_rows, params=params)
    print(f"\nOwner edges written: {len(owner_rows)} HAS_OWNER, {len(no_owner_rows)} HAS_NO_OWNER.")

    schema_branch = db.schema.get_schema_branch(name=default_branch.name)
    return OwnedDataSet(
        data_set=data_set, branch=default_branch, parents=_parent_relationships(schema_branch=schema_branch)
    )


@pytest.mark.timeout(36000)  # 10 hours, the load of the full data set is long
class TestPlainCypher(TestInfrahubApp):
    async def test_owner_filter_on_interfaces(self, db: InfrahubDatabase, owned_data_set: OwnedDataSet) -> None:
        branch = owned_data_set.branch
        groups = owned_data_set.data_set.group_ids
        expected, nb_owned = owned_data_set.expected_interfaces()
        cases: dict[str, tuple[list[str], int]] = {
            "one group, own owner of devices": ([groups[0]], expected[0]),
            "one group, second owner of 1 device in 8": ([groups[SECOND_DEVICE_GROUP]], expected[SECOND_DEVICE_GROUP]),
            "one group, owner of a location of level 3": ([groups[41]], expected[41]),
            "one group, owner of a location of level 1": ([groups[42]], expected[42]),
            "one group, own owner of interfaces": ([groups[INTERFACE_GROUP]], expected[INTERFACE_GROUP]),
            "all groups": (groups, nb_owned),
        }
        from_owners = _nodes_of_owners(branch, INTERFACE_KIND)
        rows: list[str] = []
        for name, (owner_ids, expected_count) in cases.items():
            params = owned_data_set.params(kinds=[*LOCATION_KINDS, DEVICE_KIND, INTERFACE_KIND], owner_ids=owner_ids)
            count_ms, count_rows = await _measure(db=db, query=from_owners + COUNT, params=params)
            page_ms, page_rows = await _measure(db=db, query=from_owners + PAGE, params=params)
            assert count_rows[0]["count"] == expected_count
            assert len(page_rows[0]["page"]) == min(PAGE_SIZE, expected_count)
            db_hits = await _db_hits(db=db, query=from_owners + COUNT, params=params)
            total = [count + page for count, page in zip(count_ms, page_ms, strict=True)]
            rows.append(
                f"{name} | {expected_count} | {_stats(count_ms)} | {_stats(page_ms)} | {_stats(total)} | {db_hits}"
            )

        _report(
            "Owner filter on interfaces, from the owner down",
            "Filter | Interfaces that match | Count: median (ms) | min | max | Page of 50: median (ms) | min | max"
            " | Count and page: median (ms) | min | max | db hits of the count",
            rows,
        )

    async def test_owner_filter_on_interfaces_walk_up(self, db: InfrahubDatabase, owned_data_set: OwnedDataSet) -> None:
        expected, _ = owned_data_set.expected_interfaces()
        query = _nodes_of_owners_walk_up(owned_data_set.branch, INTERFACE_KIND) + COUNT
        params = owned_data_set.params(owner_ids=[owned_data_set.data_set.group_ids[42]])

        durations, rows = await _measure(db=db, query=query, params=params, runs=1, warmup=0)

        assert rows[0]["count"] == expected[42]
        _report(
            "Owner filter on interfaces, walk up from each interface, one run",
            "Filter | Interfaces that match | Count (ms)",
            [f"one group, owner of a location of level 1 | {expected[42]} | {durations[0]:.1f}"],
        )

    async def test_no_owner_filter_on_devices(self, db: InfrahubDatabase, owned_data_set: OwnedDataSet) -> None:
        branch = owned_data_set.branch
        expected_count = sum(
            not device_owners(device, owned_data_set.nb_leaf_locations)[0] for device in range(NB_DEVICES)
        )
        queries = {
            "walk up from each device": (_nodes_without_owner_walk_up(branch, DEVICE_KIND), None),
            "from the owners down": (
                _nodes_without_owner_from_owners(branch, DEVICE_KIND),
                [*LOCATION_KINDS, DEVICE_KIND],
            ),
        }
        rows: list[str] = []
        for name, (query, kinds) in queries.items():
            params = owned_data_set.params(kinds=kinds)
            count_ms, count_rows = await _measure(db=db, query=query + COUNT, params=params)
            page_ms, page_rows = await _measure(db=db, query=query + PAGE, params=params)
            assert count_rows[0]["count"] == expected_count
            assert len(page_rows[0]["page"]) == min(PAGE_SIZE, expected_count)
            total = [count + page for count, page in zip(count_ms, page_ms, strict=True)]
            rows.append(f"{name} | {expected_count} | {_stats(count_ms)} | {_stats(page_ms)} | {_stats(total)}")

        _report(
            'Filter "no owner" on devices',
            "Query | Devices that match | Count: median (ms) | min | max | Page of 50: median (ms) | min | max"
            " | Count and page: median (ms) | min | max",
            rows,
        )

    async def test_owners_of_a_page(self, db: InfrahubDatabase, owned_data_set: OwnedDataSet) -> None:
        data_set = owned_data_set.data_set
        groups = data_set.group_ids
        device_ids = data_set.device_ids
        query = _applying_owners_query(owned_data_set.branch)

        pages: dict[str, tuple[list[str], list[str]]] = {
            "50 devices, the first of the data set": (device_ids[:PAGE_SIZE], []),
        }
        for name, owned, owners in (
            ("50 interfaces, owners from a location 6 parents above", True, [groups[42]]),
            ("50 interfaces, no owner on the 6 parents", False, []),
        ):
            devices = owned_data_set.devices(depth=LOCATION_DEPTH, owned=owned, count=NB_DEVICES_OF_A_PAGE)
            if len(devices) == NB_DEVICES_OF_A_PAGE:
                interfaces = await _interface_ids(db=db, device_ids=[device_ids[device] for device in devices])
                pages[name] = (list(interfaces.values())[:PAGE_SIZE], owners)

        rows: list[str] = []
        for name, (node_ids, owners) in pages.items():
            assert len(node_ids) == PAGE_SIZE
            params = owned_data_set.params(node_ids=node_ids)
            durations, result = await _measure(db=db, query=query, params=params, runs=30, warmup=3)
            if name.startswith("50 interfaces"):
                assert len(result) == (PAGE_SIZE if owners else 0)
                assert all(sorted(row["owner_ids"]) == owners and row["depth"] == LOCATION_DEPTH + 1 for row in result)
            rows.append(f"{name} | {_stats(durations)} | {await _db_hits(db=db, query=query, params=params)}")

        _report("Read of the owners that apply to a page", "Page | Median (ms) | min | max | db hits", rows)

    async def test_owner_change_shows_on_inheriting_nodes(
        self, db: InfrahubDatabase, owned_data_set: OwnedDataSet
    ) -> None:
        data_set = owned_data_set.data_set
        groups = data_set.group_ids
        device_id = data_set.device_ids[0]
        interface_ids = list((await _interface_ids(db=db, device_ids=[device_id])).values())
        assert len(interface_ids) == NB_INTERFACES_PER_DEVICE

        before = await _applying_owners(db=db, owned=owned_data_set, node_ids=interface_ids)
        assert set(before.values()) == {(device_id, 1, tuple(sorted([groups[0], groups[SECOND_DEVICE_GROUP]])))}

        repository = OwnershipRepository(db=db, branch=owned_data_set.branch, at=None)
        start = time.perf_counter()
        await repository.write(
            node_id=device_id,
            holder=NODE_HOLDER,
            state=StoredOwnerState(owner_ids=(groups[NEW_GROUP],)),
            write_branch=owned_data_set.branch,
            at=Timestamp(),
            user_id=SYSTEM_USER_ID,
        )
        write_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        after = await _applying_owners(db=db, owned=owned_data_set, node_ids=interface_ids)
        read_ms = (time.perf_counter() - start) * 1000

        assert set(after) == set(interface_ids)
        assert set(after.values()) == {(device_id, 1, (groups[NEW_GROUP],))}
        later_reads, _ = await _measure(
            db=db,
            query=_applying_owners_query(owned_data_set.branch),
            params=owned_data_set.params(node_ids=interface_ids),
            runs=30,
            warmup=0,
        )
        _report(
            "Change of the owners of one device, then read of its 48 interfaces",
            "Step | Median (ms) | min | max",
            [
                f"write of the owners of the device, one run | {write_ms:.1f} | |",
                f"first read of the 48 interfaces after the write, one run | {read_ms:.1f} | |",
                f"30 more reads of the 48 interfaces | {_stats(later_reads)}",
            ],
        )

    async def _mutations_with_and_without_owner_read(
        self,
        db: InfrahubDatabase,
        owned: OwnedDataSet,
        source: str,
        variables: list[Callable[[str], dict[str, Any]]],
        interface_ids: list[str],
        warmup: int,
    ) -> tuple[list[float], list[float], list[float]]:
        """Return the durations of each mutation alone, of the read of the owners, and of the read with the mutation."""
        plain: list[float] = []
        reads: list[float] = []
        checked: list[float] = []
        for run, (build_variables, interface_id) in enumerate(zip(variables, interface_ids, strict=True)):
            durations: dict[bool, float] = {}
            # The order alternates, so that a slow moment of the machine does not always hit the same side.
            for with_read in (run % 2 == 0, run % 2 != 0):
                read_ms = 0.0
                if with_read:
                    start = time.perf_counter()
                    await _applying_owners(db=db, owned=owned, node_ids=[interface_id])
                    read_ms = (time.perf_counter() - start) * 1000
                    reads.append(read_ms)
                mutation_ms = await _timed(
                    db=db, branch=owned.branch, source=source, variables=build_variables(f"{run} {with_read}")
                )
                durations[with_read] = read_ms + mutation_ms
            plain.append(durations[False])
            checked.append(durations[True])
        return plain[warmup:], reads[warmup:], checked[warmup:]

    async def test_owner_read_before_a_mutation(self, db: InfrahubDatabase, owned_data_set: OwnedDataSet) -> None:
        devices = owned_data_set.devices(depth=LOCATION_DEPTH, owned=True, count=1)
        device_id = owned_data_set.data_set.device_ids[devices[0]]
        interface_id = (await _interface_ids(db=db, device_ids=[device_id], names=["eth5"]))[device_id, "eth5"]
        owners = await _applying_owners(db=db, owned=owned_data_set, node_ids=[interface_id])
        assert owners[interface_id][1] == LOCATION_DEPTH + 1

        nb_runs = NB_MUTATION_WARMUP_RUNS + NB_MUTATION_RUNS
        plain, reads, checked = await self._mutations_with_and_without_owner_read(
            db=db,
            owned=owned_data_set,
            source=UPDATE,
            variables=[lambda text: {"id": interface_id, "description": text}] * nb_runs,
            interface_ids=[interface_id] * nb_runs,
            warmup=NB_MUTATION_WARMUP_RUNS,
        )
        added = (statistics.median(checked) / statistics.median(plain) - 1) * 100
        _report(
            f"Update of one interface with its owners 6 parents above, {NB_MUTATION_RUNS} runs",
            "Operation | Median (ms) | min | max",
            [
                f"update alone | {_stats(plain)}",
                f"read of the owners that apply | {_stats(reads)}",
                f"read, then update | {_stats(checked)}",
                f"added by the read, on the medians | {added:.1f}% | |",
            ],
        )

    async def test_owner_read_before_each_upsert_of_a_generator(
        self, db: InfrahubDatabase, owned_data_set: OwnedDataSet
    ) -> None:
        device_ids = owned_data_set.data_set.device_ids
        owned_devices = [device_ids[device] for device in range(4, NB_DEVICES, 4)]
        nb_devices = -(-NB_GENERATOR_NODES // NB_INTERFACES_PER_DEVICE)
        interfaces = list((await _interface_ids(db=db, device_ids=owned_devices[:nb_devices])).items())
        interfaces = interfaces[:NB_GENERATOR_NODES]

        def variables(device_id: str, name: str) -> Callable[[str], dict[str, Any]]:
            return lambda text: {"name": name, "device": device_id, "description": text}

        plain, reads, checked = await self._mutations_with_and_without_owner_read(
            db=db,
            owned=owned_data_set,
            source=UPSERT,
            variables=[variables(device_id, name) for (device_id, name), _ in interfaces],
            interface_ids=[interface_id for _, interface_id in interfaces],
            warmup=0,
        )
        added = (sum(checked) / sum(plain) - 1) * 100
        added_on_medians = (statistics.median(checked) / statistics.median(plain) - 1) * 100
        _report(
            f"Upsert of {len(interfaces)} interfaces whose device has own owners",
            "Operation | Total (s) | Median (ms) | min | max",
            [
                f"upsert alone | {sum(plain) / 1000:.1f} | {_stats(plain)}",
                f"read of the owners that apply | {sum(reads) / 1000:.1f} | {_stats(reads)}",
                f"read, then upsert | {sum(checked) / 1000:.1f} | {_stats(checked)}",
                f"added by the read, on the totals | {added:.1f}% | | |",
                f"added by the read, on the medians | | {added_on_medians:.1f}% | |",
            ],
        )

    async def test_owner_set_lookup_by_key(self, db: InfrahubDatabase, owned_data_set: OwnedDataSet) -> None:
        data_set = owned_data_set.data_set
        group_id = data_set.group_ids[44]
        devices = data_set.device_ids[1 : 1 + NB_OWNER_SETS]
        rows = [(device_id, INTERFACES_IDENTIFIER, group_id) for device_id in devices]
        rows += [(devices[0], f"field_{index:02d}", group_id) for index in range(NB_OWNER_SETS_OF_ONE_NODE - 1)]
        await _write(db=db, query=SET_FIELD_OWNERS, rows=rows, params=_edge_params(branch=owned_data_set.branch))

        query = OWNER_SET_LOOKUP % {"active": _active(owned_data_set.branch, "r")}
        report: list[str] = []
        for name, device_id in (
            (f"node with {NB_OWNER_SETS_OF_ONE_NODE} OwnerSet vertices", devices[0]),
            ("node with 1 OwnerSet vertex", devices[1]),
        ):
            params = owned_data_set.params(node_id=device_id, identifier=INTERFACES_IDENTIFIER)
            durations, result = await _measure(db=db, query=query, params=params, runs=30, warmup=3)
            assert len(result) == 1
            report.append(f"{name} | {_stats(durations)} | {await _db_hits(db=db, query=query, params=params)}")

        _report(
            f"Lookup of an OwnerSet by its key, without an index, {len(rows)} OwnerSet vertices in the database",
            "Node | Median (ms) | min | max | db hits",
            report,
        )

    async def test_diff_of_owner_changes_with_and_without_index(
        self, db: InfrahubDatabase, owned_data_set: OwnedDataSet
    ) -> None:
        data_set = owned_data_set.data_set
        device_ids = data_set.device_ids
        from_time = Timestamp().to_string()
        branch_params = {**_edge_params(branch=owned_data_set.branch), "branch": DIFF_BRANCH, "branch_level": 2}
        owner_rows = [(device_ids[device], data_set.group_ids[45]) for device in range(3, NB_DEVICES, 4)]
        no_owner_rows = [device_ids[device] for device in range(2, NB_DEVICES, 4)]
        owner_rows, no_owner_rows = owner_rows[:NB_BRANCH_CHANGES], no_owner_rows[:NB_BRANCH_CHANGES]
        await _write(db=db, query=SET_OWNERS, rows=owner_rows, params=branch_params)
        await _write(db=db, query=SET_NO_OWNER, rows=no_owner_rows, params=branch_params)
        nb_changes = len(owner_rows) + len(no_owner_rows)

        index = IndexRelNeo4j(**next(item for item in rel_indexes if item.label == "HAS_NO_OWNER").model_dump())
        count_no_owner = "MATCH ()-[r:HAS_NO_OWNER]->() RETURN count(r) AS count"
        rows: list[str] = []

        async def measure(with_index: bool) -> None:
            nb_edges = (await db.execute_query(query=count_no_owner))[0]["count"]
            query = _diff_query(hinted_edge_types=["HAS_OWNER", "HAS_NO_OWNER"] if with_index else ["HAS_OWNER"])
            params = {"branch": DIFF_BRANCH, "from_time": from_time, "to_time": Timestamp().to_string()}
            durations, result = await _measure(db=db, query=query, params=params, runs=30, warmup=3)
            assert len(result) == nb_changes
            db_hits = await _db_hits(db=db, query=query, params=params)
            rows.append(
                f"{'yes' if with_index else 'no'} | {nb_edges} | {nb_changes} | {_stats(durations)} | {db_hits}"
            )

        async def set_index(present: bool) -> None:
            await db.execute_query(query=index.get_add_query() if present else index.get_drop_query())
            await db.execute_query(query="CALL db.awaitIndexes(600)")

        try:
            for add_no_owner_edges in (False, True):
                if add_no_owner_edges:
                    interfaces = await _interface_ids(db=db, device_ids=device_ids, names=NO_OWNER_PORTS)
                    await _write(
                        db=db,
                        query=SET_NO_OWNER,
                        rows=list(interfaces.values()),
                        params=_edge_params(branch=owned_data_set.branch),
                    )
                await measure(with_index=True)
                await set_index(present=False)
                await measure(with_index=False)
                await set_index(present=True)
        finally:
            await set_index(present=True)

        _report(
            "Diff of the owner changes of a branch, with and without the index on the branch of HAS_NO_OWNER",
            "Index | HAS_NO_OWNER edges in the database | Changes on the branch | Median (ms) | min | max | db hits",
            rows,
        )

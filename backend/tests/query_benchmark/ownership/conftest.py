from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.helpers.planner_statistics import refresh_planner_statistics
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

# The reference data set has 10,000 devices. A smaller number gives a faster load on a shared machine.
NB_DEVICES = int(os.environ.get("INFRAHUB_OWNERSHIP_BENCHMARK_DEVICES", "10000"))
NB_INTERFACES_PER_DEVICE = 48
NB_ACCOUNT_GROUPS = 50
LOCATION_LEVELS = ("Region", "Country", "Metro", "Site", "Rack")
LOCATIONS_PER_PARENT = 3
# Each write opens a database session, so this number stays below the size of the connection pool.
NB_CONCURRENT_WRITES = 32

DEVICE_KIND = "BenchDevice"
INTERFACE_KIND = "BenchInterface"
RACK_KIND = f"Bench{LOCATION_LEVELS[-1]}"

REFERENCE_SCHEMA = SchemaRoot(
    generics=[
        GenericSchema(
            name="Location",
            namespace="Bench",
            hierarchical=True,
            default_filter="name__value",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        )
    ],
    nodes=[
        *[
            NodeSchema(
                name=level,
                namespace="Bench",
                inherit_from=["BenchLocation"],
                default_filter="name__value",
                parent=f"Bench{LOCATION_LEVELS[index - 1]}" if index else "",
                children=f"Bench{LOCATION_LEVELS[index + 1]}" if index + 1 < len(LOCATION_LEVELS) else "",
                generate_profile=False,
            )
            for index, level in enumerate(LOCATION_LEVELS)
        ],
        NodeSchema(
            name="Device",
            namespace="Bench",
            default_filter="name__value",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="role", kind="Text"),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="rack",
                    kind=RelationshipKind.PARENT,
                    optional=False,
                    peer=RACK_KIND,
                    cardinality=RelationshipCardinality.ONE,
                ),
                RelationshipSchema(
                    name="interfaces",
                    kind=RelationshipKind.COMPONENT,
                    optional=True,
                    peer=INTERFACE_KIND,
                    cardinality=RelationshipCardinality.MANY,
                    identifier="benchdevice__interfaces",
                ),
            ],
        ),
        NodeSchema(
            name="Interface",
            namespace="Bench",
            default_filter="name__value",
            human_friendly_id=["device__name__value", "name__value"],
            uniqueness_constraints=[["device", "name__value"]],
            attributes=[
                AttributeSchema(name="name", kind="Text"),
                AttributeSchema(name="enabled", kind="Boolean", default_value=True),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="device",
                    kind=RelationshipKind.PARENT,
                    optional=False,
                    peer=DEVICE_KIND,
                    cardinality=RelationshipCardinality.ONE,
                    identifier="benchdevice__interfaces",
                )
            ],
        ),
    ],
)


@dataclass(frozen=True)
class ReferenceDataSet:
    location_ids: dict[str, list[str]]
    """IDs of the locations of each level, from the top level down to the racks."""

    device_ids: list[str]
    nb_interfaces: int


async def _create(db: InfrahubDatabase, limit: asyncio.Semaphore, kind: str, **data: str | Node) -> Node:
    # Concurrent queries cannot share a session.
    async with limit, db.start_session() as session_db:
        node = await Node.init(db=session_db, schema=kind)
        await node.new(db=session_db, id=None, process_pools=True, **data)
        await node.save(db=session_db)
    return node


async def load_reference_data_set(db: InfrahubDatabase, nb_devices: int = NB_DEVICES) -> ReferenceDataSet:
    """Write the reference data set on the default branch, with no owner on any node."""
    await load_schema(db=db, schema=REFERENCE_SCHEMA)
    limit = asyncio.Semaphore(NB_CONCURRENT_WRITES)

    await asyncio.gather(
        *[
            _create(db, limit, InfrahubKind.ACCOUNTGROUP, name=f"owner-group-{index:02d}")
            for index in range(NB_ACCOUNT_GROUPS)
        ]
    )

    location_ids: dict[str, list[str]] = {}
    parents: list[Node | None] = [None]
    for level in LOCATION_LEVELS:
        parents = list(
            await asyncio.gather(
                *[
                    _create(
                        db,
                        limit,
                        f"Bench{level}",
                        name=f"{level.lower()}-{parent_index}-{index}",
                        **({"parent": parent} if parent else {}),
                    )
                    for parent_index, parent in enumerate(parents)
                    for index in range(LOCATIONS_PER_PARENT)
                ]
            )
        )
        location_ids[level] = [location.get_id() for location in parents if location]
    racks = [rack for rack in parents if rack]

    device_ids: list[str] = []
    # One batch at a time, so the nodes in memory stay bounded for the full size.
    for start in range(0, nb_devices, NB_CONCURRENT_WRITES):
        devices = await asyncio.gather(
            *[
                _create(db, limit, DEVICE_KIND, name=f"device-{index:05d}", role="leaf", rack=racks[index % len(racks)])
                for index in range(start, min(start + NB_CONCURRENT_WRITES, nb_devices))
            ]
        )
        await asyncio.gather(
            *[
                _create(db, limit, INTERFACE_KIND, name=f"eth{number}", device=device)
                for device in devices
                for number in range(NB_INTERFACES_PER_DEVICE)
            ]
        )
        device_ids.extend(device.get_id() for device in devices)

    # Neo4j made its query plans for the empty graph, and the load is faster than its own resampling.
    await refresh_planner_statistics(db=db)
    return ReferenceDataSet(
        location_ids=location_ids,
        device_ids=device_ids,
        nb_interfaces=nb_devices * NB_INTERFACES_PER_DEVICE,
    )


@pytest.fixture(scope="session")
def neo4j_heap_size() -> str:
    """Larger than the test default, so the numbers measure the queries and not the memory limit."""
    return "4.00GiB"


@pytest.fixture(scope="session")
def neo4j_pagecache_size() -> str:
    """Large enough to hold the data set, so the numbers measure the queries and not the disk."""
    return "4.00GiB"


@pytest.fixture(scope="class")
async def reference_data_set(db: InfrahubDatabase, initialize_registry: None) -> ReferenceDataSet:
    """Reference data set of the success criteria, for a test class that runs the application in process."""
    return await load_reference_data_set(db=db)

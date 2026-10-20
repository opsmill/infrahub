"""A pooled number reports its pool as `source` through the reads that do not go through the list resolver.

A `descendants` or `ancestors` read loads the nodes of a hierarchy, and the `BuiltinIPPrefix` query loads
prefixes of every kind that implements it. Both have to ask for the tracking pool the way the list resolver
does, or the number reports its stored source instead of the pool.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema
from tests.helpers.number_pool import add_pool_range
from tests.helpers.schema import load_schema

from .helpers import attribute_read, execute, pool_source

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import SchemaRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

RANK_SOURCES_OF_DESCENDANTS = """
query RankSourcesOfDescendants($id: ID!) {
    LocationRegion(ids: [$id]) {
        edges { node { descendants { edges { node { id rank { value source { id __typename } } } } } } }
    }
}
"""

RANK_SOURCES_OF_ANCESTORS = """
query RankSourcesOfAncestors($id: ID!) {
    LocationRack(ids: [$id]) {
        edges { node { ancestors { edges { node { id rank { value source { id __typename } } } } } } }
    }
}
"""

VLAN_SOURCES_OF_PREFIXES = """
query VlanSourcesOfPrefixes($id: ID!) {
    BuiltinIPPrefix(ids: [$id]) {
        edges { node { id ... on IpamIPPrefix { vlan_id { value source { id __typename } } } } }
    }
}
"""


async def new_pool(db: InfrahubDatabase, name: str, node: str, node_attribute: str) -> CoreNumberPool:
    pool = await CoreNumberPool.init(db=db, schema=InfrahubKind.NUMBERPOOL)
    await pool.new(db=db, name=name, node=node, node_attribute=node_attribute, start_range=1, end_range=20)
    await pool.save(db=db)
    await add_pool_range(db=db, pool=pool, start=1, end=20)
    return pool


def sources_of(edges: list[dict[str, Any]], attribute_name: str) -> dict[str, Any]:
    return {edge["node"]["id"]: attribute_read(edge["node"][attribute_name]) for edge in edges}


@pytest.fixture
async def location_hierarchy_with_rank(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    hierarchical_location_schema_simple_unregistered: SchemaRoot,
) -> None:
    """The location hierarchy, where every location has a `rank` number a pool can track."""
    schema = deepcopy(hierarchical_location_schema_simple_unregistered)
    [generic] = schema.generics
    generic.attributes.append(AttributeSchema(name="rank", kind="Number", optional=True))
    await load_schema(db=db, schema=schema)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


async def test_a_hierarchy_read_reports_the_pool_of_every_location(
    db: InfrahubDatabase, default_branch: Branch, location_hierarchy_with_rank: None
) -> None:
    pool = await new_pool(db=db, name="ranks", node="LocationGeneric", node_attribute="rank")
    region = await Node.init(db=db, schema="LocationRegion", branch=default_branch)
    await region.new(db=db, name="europe", rank={"from_pool": {"id": pool.id}})
    await region.save(db=db)
    site = await Node.init(db=db, schema="LocationSite", branch=default_branch)
    await site.new(db=db, name="paris", parent=region, rank={"from_pool": {"id": pool.id}})
    await site.save(db=db)
    rack = await Node.init(db=db, schema="LocationRack", branch=default_branch)
    await rack.new(db=db, name="rack-1", parent=site, rank={"from_pool": {"id": pool.id}})
    await rack.save(db=db)

    descendants = await execute(
        db=db, branch=default_branch, source=RANK_SOURCES_OF_DESCENDANTS, variables={"id": region.id}
    )
    assert descendants
    [region_edge] = descendants["LocationRegion"]["edges"]
    assert sources_of(region_edge["node"]["descendants"]["edges"], "rank") == {
        site.id: pool_source(value=2, pool=pool),
        rack.id: pool_source(value=3, pool=pool),
    }

    ancestors = await execute(db=db, branch=default_branch, source=RANK_SOURCES_OF_ANCESTORS, variables={"id": rack.id})
    assert ancestors
    [rack_edge] = ancestors["LocationRack"]["edges"]
    assert sources_of(rack_edge["node"]["ancestors"]["edges"], "rank") == {
        region.id: pool_source(value=1, pool=pool),
        site.id: pool_source(value=2, pool=pool),
    }


@pytest.fixture
async def prefix_kind_with_vlan(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, ipam_schema: SchemaRoot
) -> None:
    """The IPAM prefix kind, with a `vlan_id` number the generic prefix query only reaches through a fragment."""
    schema = deepcopy(ipam_schema)
    [prefix_kind] = [node for node in schema.nodes if node.kind == "IpamIPPrefix"]
    prefix_kind.attributes.append(AttributeSchema(name="vlan_id", kind="Number", optional=True))
    await load_schema(db=db, schema=schema)
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


async def test_the_generic_prefix_query_reports_the_pool_of_an_implementer_number(
    db: InfrahubDatabase, default_branch: Branch, prefix_kind_with_vlan: None
) -> None:
    pool = await new_pool(db=db, name="vlans", node="IpamIPPrefix", node_attribute="vlan_id")
    namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE, branch=default_branch)
    await namespace.new(db=db, name="ns1")
    await namespace.save(db=db)
    prefix = await Node.init(db=db, schema="IpamIPPrefix", branch=default_branch)
    await prefix.new(db=db, prefix="10.0.0.0/8", ip_namespace=namespace, vlan_id={"from_pool": {"id": pool.id}})
    await prefix.save(db=db)

    data = await execute(db=db, branch=default_branch, source=VLAN_SOURCES_OF_PREFIXES, variables={"id": prefix.id})
    assert data
    assert sources_of(data["BuiltinIPPrefix"]["edges"], "vlan_id") == {prefix.id: pool_source(value=1, pool=pool)}

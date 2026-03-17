"""Functional tests for virtual relationships.

These tests require a running Neo4j database and test the full stack:
schema loading → data creation → Cypher traversal → GraphQL resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema, SchemaRoot, VirtualRelationshipSchema
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

# ---------------------------------------------------------------------------
# Schema definitions for tests
# ---------------------------------------------------------------------------

DEVICE_WITH_VR_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Chassis",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text", "unique": True}],
            relationships=[
                {
                    "name": "bays",
                    "peer": "TestingBay",
                    "cardinality": "many",
                    "kind": "Component",
                }
            ],
            virtual_relationships=[
                VirtualRelationshipSchema(
                    name="all_modules",
                    label="All Modules",
                    path="bays__modules",
                ),
            ],
        ),
        NodeSchema(
            name="Bay",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text"}],
            relationships=[
                {
                    "name": "chassis",
                    "peer": "TestingChassis",
                    "cardinality": "one",
                    "kind": "Parent",
                    "optional": False,
                },
                {
                    "name": "modules",
                    "peer": "TestingModule",
                    "cardinality": "many",
                    "kind": "Component",
                },
            ],
        ),
        NodeSchema(
            name="Module",
            namespace="Testing",
            attributes=[
                {"name": "name", "kind": "Text"},
                {"name": "model", "kind": "Text", "optional": True},
            ],
            relationships=[
                {
                    "name": "bay",
                    "peer": "TestingBay",
                    "cardinality": "one",
                    "kind": "Parent",
                    "optional": False,
                },
            ],
        ),
    ],
)


class TestVirtualRelationshipQuery(TestInfrahubApp):
    """T017: Load schema, create data, query via GraphQL."""

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, str]:
        await load_schema(db, schema=DEVICE_WITH_VR_SCHEMA, update_db=True)

        # Create: Chassis → 2 Bays → 2 Modules each = 4 modules total
        chassis = await Node.init(db=db, schema="TestingChassis")
        await chassis.new(db=db, name="chassis-01")
        await chassis.save(db=db)

        bay1 = await Node.init(db=db, schema="TestingBay")
        await bay1.new(db=db, name="bay-1", chassis=chassis)
        await bay1.save(db=db)

        bay2 = await Node.init(db=db, schema="TestingBay")
        await bay2.new(db=db, name="bay-2", chassis=chassis)
        await bay2.save(db=db)

        mod1 = await Node.init(db=db, schema="TestingModule")
        await mod1.new(db=db, name="mod-1a", model="X100", bay=bay1)
        await mod1.save(db=db)

        mod2 = await Node.init(db=db, schema="TestingModule")
        await mod2.new(db=db, name="mod-1b", model="X200", bay=bay1)
        await mod2.save(db=db)

        mod3 = await Node.init(db=db, schema="TestingModule")
        await mod3.new(db=db, name="mod-2a", model="X100", bay=bay2)
        await mod3.save(db=db)

        mod4 = await Node.init(db=db, schema="TestingModule")
        await mod4.new(db=db, name="mod-2b", model="X300", bay=bay2)
        await mod4.save(db=db)

        # Create a chassis with no bays (for empty result test)
        empty_chassis = await Node.init(db=db, schema="TestingChassis")
        await empty_chassis.new(db=db, name="chassis-empty")
        await empty_chassis.save(db=db)

        return {
            "chassis_id": chassis.id,
            "empty_chassis_id": empty_chassis.id,
            "mod1_id": mod1.id,
            "mod2_id": mod2.id,
            "mod3_id": mod3.id,
            "mod4_id": mod4.id,
        }

    async def test_query_virtual_relationship_returns_all_targets(
        self, initial_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T017: Query virtual relationship returns all target nodes."""
        query = """
        query GetChassis($id: [ID!]) {
            TestingChassis(ids: $id) {
                edges {
                    node {
                        name { value }
                        all_modules {
                            count
                            edges {
                                node {
                                    id
                                    name { value }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [initial_dataset["chassis_id"]]})
        chassis = response["TestingChassis"]["edges"][0]["node"]
        assert chassis["name"]["value"] == "chassis-01"
        assert chassis["all_modules"]["count"] == 4

        module_names = sorted(edge["node"]["name"]["value"] for edge in chassis["all_modules"]["edges"])
        assert module_names == ["mod-1a", "mod-1b", "mod-2a", "mod-2b"]

    async def test_virtual_relationship_empty_result(
        self, initial_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T021: Empty collection returned when path resolves to zero nodes."""
        query = """
        query GetEmptyChassis($id: [ID!]) {
            TestingChassis(ids: $id) {
                edges {
                    node {
                        all_modules {
                            count
                            edges {
                                node {
                                    name { value }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [initial_dataset["empty_chassis_id"]]})
        chassis = response["TestingChassis"]["edges"][0]["node"]
        assert chassis["all_modules"]["count"] == 0
        assert chassis["all_modules"]["edges"] == []

    async def test_virtual_relationship_pagination(
        self, initial_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T020: Pagination (offset/limit) on virtual relationship results."""
        query = """
        query GetChassisPage($id: [ID!]) {
            TestingChassis(ids: $id) {
                edges {
                    node {
                        all_modules(limit: 2, offset: 0) {
                            count
                            edges {
                                node {
                                    name { value }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [initial_dataset["chassis_id"]]})
        chassis = response["TestingChassis"]["edges"][0]["node"]
        # Count should reflect total, edges limited to 2
        assert len(chassis["all_modules"]["edges"]) == 2

    async def test_virtual_relationship_filtering(
        self, initial_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T019: Filtering on virtual relationship results by attribute value."""
        query = """
        query GetChassisFiltered($id: [ID!]) {
            TestingChassis(ids: $id) {
                edges {
                    node {
                        all_modules(model__value: "X100") {
                            count
                            edges {
                                node {
                                    name { value }
                                    model { value }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [initial_dataset["chassis_id"]]})
        chassis = response["TestingChassis"]["edges"][0]["node"]
        # Edges should only contain modules with model=X100
        module_models = [edge["node"]["model"]["value"] for edge in chassis["all_modules"]["edges"]]
        assert all(m == "X100" for m in module_models)
        assert len(module_models) == 2


class TestVirtualRelationshipBranchAware(TestInfrahubApp):
    """T023: Branch-aware resolution of virtual relationships."""

    @pytest.fixture(scope="class")
    async def branch_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, str]:
        await load_schema(db, schema=DEVICE_WITH_VR_SCHEMA, update_db=True)

        # Create baseline data on main
        chassis = await Node.init(db=db, schema="TestingChassis")
        await chassis.new(db=db, name="branch-chassis")
        await chassis.save(db=db)

        bay = await Node.init(db=db, schema="TestingBay")
        await bay.new(db=db, name="branch-bay", chassis=chassis)
        await bay.save(db=db)

        mod_main = await Node.init(db=db, schema="TestingModule")
        await mod_main.new(db=db, name="mod-main-only", bay=bay)
        await mod_main.save(db=db)

        # Create a branch and add data only there
        await client.branch.create(branch_name="vr-test-branch")

        mod_branch = await client.create(
            kind="TestingModule",
            data={"name": "mod-branch-only", "bay": {"id": bay.id}},
            branch="vr-test-branch",
        )
        await mod_branch.save()

        return {
            "chassis_id": chassis.id,
            "branch_name": "vr-test-branch",
        }

    async def test_main_branch_sees_only_main_data(
        self, branch_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T023: Main branch query returns only main branch modules."""
        query = """
        query ($id: [ID!]) {
            TestingChassis(ids: $id) {
                edges {
                    node {
                        all_modules {
                            count
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [branch_dataset["chassis_id"]]})
        modules = response["TestingChassis"]["edges"][0]["node"]["all_modules"]
        module_names = [e["node"]["name"]["value"] for e in modules["edges"]]
        assert "mod-main-only" in module_names
        assert "mod-branch-only" not in module_names

    async def test_branch_sees_both_main_and_branch_data(
        self, branch_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T023: Branch query returns both main and branch modules."""
        query = """
        query ($id: [ID!]) {
            TestingChassis(ids: $id) {
                edges {
                    node {
                        all_modules {
                            count
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(
            query=query,
            variables={"id": [branch_dataset["chassis_id"]]},
            branch_name=branch_dataset["branch_name"],
        )
        modules = response["TestingChassis"]["edges"][0]["node"]["all_modules"]
        module_names = [e["node"]["name"]["value"] for e in modules["edges"]]
        assert "mod-main-only" in module_names
        assert "mod-branch-only" in module_names


# ---------------------------------------------------------------------------
# Cross-domain schema for T029/T030 tests
# ---------------------------------------------------------------------------

CROSS_DOMAIN_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Router",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text", "unique": True}],
            relationships=[
                {"name": "ports", "peer": "TestingPort", "cardinality": "many", "kind": "Component"},
            ],
            virtual_relationships=[
                VirtualRelationshipSchema(name="all_services", path="ports__circuits__services"),
            ],
        ),
        NodeSchema(
            name="Port",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text"}],
            relationships=[
                {"name": "router", "peer": "TestingRouter", "cardinality": "one", "kind": "Parent", "optional": False},
                {"name": "circuits", "peer": "TestingCircuit", "cardinality": "many"},
            ],
        ),
        NodeSchema(
            name="Circuit",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text"}],
            relationships=[
                {"name": "ports", "peer": "TestingPort", "cardinality": "many"},
                {"name": "services", "peer": "TestingService", "cardinality": "many"},
            ],
        ),
        NodeSchema(
            name="Service",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text"}],
            relationships=[
                {"name": "circuits", "peer": "TestingCircuit", "cardinality": "many"},
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Dedup schema for T022 — Module reachable via two bays (shared)
# ---------------------------------------------------------------------------

DEDUP_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Rack",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text", "unique": True}],
            relationships=[
                {"name": "shelves", "peer": "TestingShelf", "cardinality": "many", "kind": "Component"},
            ],
            virtual_relationships=[
                VirtualRelationshipSchema(name="all_cards", path="shelves__cards"),
            ],
        ),
        NodeSchema(
            name="Shelf",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text"}],
            relationships=[
                {"name": "rack", "peer": "TestingRack", "cardinality": "one", "kind": "Parent", "optional": False},
                {"name": "cards", "peer": "TestingCard", "cardinality": "many"},
            ],
        ),
        NodeSchema(
            name="Card",
            namespace="Testing",
            attributes=[{"name": "name", "kind": "Text"}],
            relationships=[
                {"name": "shelves", "peer": "TestingShelf", "cardinality": "many"},
            ],
        ),
    ],
)


class TestVirtualRelationshipDedup(TestInfrahubApp):
    """T022: Deduplication when same target reachable via multiple paths."""

    @pytest.fixture(scope="class")
    async def dedup_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, str]:
        await load_schema(db, schema=DEDUP_SCHEMA, update_db=True)

        rack = await Node.init(db=db, schema="TestingRack")
        await rack.new(db=db, name="rack-dedup")
        await rack.save(db=db)

        shelf1 = await Node.init(db=db, schema="TestingShelf")
        await shelf1.new(db=db, name="shelf-1", rack=rack)
        await shelf1.save(db=db)

        shelf2 = await Node.init(db=db, schema="TestingShelf")
        await shelf2.new(db=db, name="shelf-2", rack=rack)
        await shelf2.save(db=db)

        # Create a card linked to BOTH shelves (reachable via two paths)
        shared_card = await Node.init(db=db, schema="TestingCard")
        await shared_card.new(db=db, name="shared-card", shelves=[shelf1, shelf2])
        await shared_card.save(db=db)

        # Create a card linked to only shelf1
        unique_card = await Node.init(db=db, schema="TestingCard")
        await unique_card.new(db=db, name="unique-card", shelves=[shelf1])
        await unique_card.save(db=db)

        return {"rack_id": rack.id}

    async def test_dedup_returns_unique_targets(self, dedup_dataset: dict[str, str], client: InfrahubClient) -> None:
        """T022: Same target reachable via multiple paths appears only once."""
        query = """
        query ($id: [ID!]) {
            TestingRack(ids: $id) {
                edges {
                    node {
                        all_cards {
                            count
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [dedup_dataset["rack_id"]]})
        cards = response["TestingRack"]["edges"][0]["node"]["all_cards"]
        card_names = sorted(e["node"]["name"]["value"] for e in cards["edges"])
        # shared-card should appear only once despite being reachable via shelf-1 and shelf-2
        assert card_names == ["shared-card", "unique-card"]
        assert cards["count"] == 2


class TestVirtualRelationshipCrossDomain(TestInfrahubApp):
    """T029-T030: Cross-domain traversal across 4 node kinds."""

    @pytest.fixture(scope="class")
    async def cross_domain_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, str]:
        await load_schema(db, schema=CROSS_DOMAIN_SCHEMA, update_db=True)

        router = await Node.init(db=db, schema="TestingRouter")
        await router.new(db=db, name="router-01")
        await router.save(db=db)

        # 2 ports
        port1 = await Node.init(db=db, schema="TestingPort")
        await port1.new(db=db, name="eth0", router=router)
        await port1.save(db=db)

        port2 = await Node.init(db=db, schema="TestingPort")
        await port2.new(db=db, name="eth1", router=router)
        await port2.save(db=db)

        # 2 circuits, each on a different port
        circuit1 = await Node.init(db=db, schema="TestingCircuit")
        await circuit1.new(db=db, name="circuit-A", ports=[port1])
        await circuit1.save(db=db)

        circuit2 = await Node.init(db=db, schema="TestingCircuit")
        await circuit2.new(db=db, name="circuit-B", ports=[port2])
        await circuit2.save(db=db)

        # 3 services: svc1 on circuit1, svc2 on circuit2, svc3 on both circuits
        svc1 = await Node.init(db=db, schema="TestingService")
        await svc1.new(db=db, name="svc-web", circuits=[circuit1])
        await svc1.save(db=db)

        svc2 = await Node.init(db=db, schema="TestingService")
        await svc2.new(db=db, name="svc-dns", circuits=[circuit2])
        await svc2.save(db=db)

        svc3 = await Node.init(db=db, schema="TestingService")
        await svc3.new(db=db, name="svc-shared", circuits=[circuit1, circuit2])
        await svc3.save(db=db)

        return {"router_id": router.id}

    async def test_cross_domain_collects_all_services(
        self, cross_domain_dataset: dict[str, str], client: InfrahubClient
    ) -> None:
        """T029: Cross-domain VR collects all target nodes across 4 node kinds."""
        query = """
        query ($id: [ID!]) {
            TestingRouter(ids: $id) {
                edges {
                    node {
                        all_services {
                            count
                            edges { node { name { value } } }
                        }
                    }
                }
            }
        }
        """
        response = await client.execute_graphql(query=query, variables={"id": [cross_domain_dataset["router_id"]]})
        services = response["TestingRouter"]["edges"][0]["node"]["all_services"]
        service_names = sorted(e["node"]["name"]["value"] for e in services["edges"])
        # svc-shared is reachable via both circuits but should appear only once
        assert service_names == ["svc-dns", "svc-shared", "svc-web"]
        assert services["count"] == 3


class TestVirtualRelationshipSchemaValidation(TestInfrahubApp):
    """T018/T037: Schema validation rejects invalid paths."""

    @pytest.fixture(scope="class")
    async def base_setup(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        await load_schema(db, schema=DEVICE_WITH_VR_SCHEMA, update_db=True)

    async def test_invalid_path_segment_rejected(self, base_setup: None, client: InfrahubClient) -> None:
        """T018: Invalid path segment is rejected at schema load time."""
        result = await client.schema.load(
            schemas=[
                {
                    "version": "1.0",
                    "nodes": [
                        {
                            "name": "BadDevice",
                            "namespace": "Testing",
                            "attributes": [{"name": "name", "kind": "Text"}],
                            "relationships": [
                                {
                                    "name": "bays",
                                    "peer": "TestingBay",
                                    "cardinality": "many",
                                    "kind": "Component",
                                }
                            ],
                            "virtual_relationships": [
                                {
                                    "name": "bad_path",
                                    "path": "bays__nonexistent_rel",
                                }
                            ],
                        }
                    ],
                }
            ]
        )
        assert not result.schema_updated

    async def test_path_too_short_rejected(self, base_setup: None, client: InfrahubClient) -> None:
        """T018: Path with less than 2 segments is rejected."""
        result = await client.schema.load(
            schemas=[
                {
                    "version": "1.0",
                    "nodes": [
                        {
                            "name": "ShortPath",
                            "namespace": "Testing",
                            "attributes": [{"name": "name", "kind": "Text"}],
                            "relationships": [
                                {
                                    "name": "bays",
                                    "peer": "TestingBay",
                                    "cardinality": "many",
                                }
                            ],
                            "virtual_relationships": [{"name": "short_vr", "path": "bays"}],
                        }
                    ],
                }
            ]
        )
        assert not result.schema_updated

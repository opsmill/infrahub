"""Functional tests for metadata queries (created_by, updated_by, created_at, updated_at).

These tests verify that metadata fields are correctly tracked and returned:
- created_by: The account that created the node/relationship
- updated_by: The account that last updated the node/attribute/relationship
- created_at: Timestamp when the node/relationship was created
- updated_at: Timestamp when the node/attribute/relationship was last updated

Tests cover metadata at three levels:
- node_metadata: Node-level metadata (created_by, updated_by, created_at, updated_at)
- Attribute metadata: Per-attribute metadata (updated_by, updated_at only)
- relationship_metadata: Relationship-level metadata (created_by, updated_by, created_at, updated_at)

Note on relationship structures:
- Single relationships (cardinality=ONE): owner { node { } relationship_metadata { } }
- Many relationships (cardinality=MANY): cars { edges { node { } relationship_metadata { } } }
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase


class TestMetadataQueries(TestInfrahubApp):
    """Test metadata queries for nodes, attributes, and relationships."""

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        admin_account: CoreAccount,
        bot_account: CoreAccount,
    ) -> dict[str, Any]:
        """Create initial test data with the admin account."""
        await load_schema(db, schema=CAR_SCHEMA)

        # Create a person using admin client
        john = await client.create(kind=TestKind.PERSON, name="John", height=175, description="The main owner")
        await john.save()

        # Create a manufacturer using admin client
        koenigsegg = await client.create(kind=TestKind.MANUFACTURER, name="Koenigsegg", description="Swedish supercar")
        await koenigsegg.save()

        # Create a car using admin client
        jesko = await client.create(
            kind=TestKind.CAR,
            name="Jesko",
            color="Red",
            description="A limited production mid-engine sports car",
            owner={"id": john.id},
            manufacturer={"id": koenigsegg.id},
        )
        await jesko.save()

        # Get display labels via db since they may be title-cased or formatted differently
        admin_display_label = await admin_account.get_display_label()
        bot_display_label = await bot_account.get_display_label()

        return {
            "john_id": john.id,
            "koenigsegg_id": koenigsegg.id,
            "jesko_id": jesko.id,
            "admin_account_id": admin_account.id,
            "admin_display_label": admin_display_label,
            "bot_display_label": bot_display_label,
        }

    async def test_node_metadata_created_by_admin(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify node_metadata shows admin as creator for initial nodes."""
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                        updated_by {
                            id
                            display_label
                        }
                        created_at
                        updated_at
                    }
                    node {
                        id
                        name { value }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        assert result["TestingCar"]["edges"]
        node_metadata = result["TestingCar"]["edges"][0]["node_metadata"]

        # Verify created_by is the admin account
        assert node_metadata["created_by"]["id"] == admin_account.id
        assert node_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]

        # Verify updated_by is also admin (no updates yet)
        assert node_metadata["updated_by"]["id"] == admin_account.id
        assert node_metadata["updated_by"]["display_label"] == initial_dataset["admin_display_label"]

        # Verify timestamps are present
        assert node_metadata["created_at"] is not None
        assert node_metadata["updated_at"] is not None

    async def test_attribute_metadata_updated_by_admin(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify attribute metadata shows admin as updater for initial attributes.

        Note: Attributes only have updated_by and updated_at, not created_by/created_at.
        """
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node {
                        id
                        name {
                            value
                            updated_by {
                                id
                                display_label
                            }
                            updated_at
                        }
                        color {
                            value
                            updated_by {
                                id
                                display_label
                            }
                            updated_at
                        }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        assert result["TestingCar"]["edges"]
        node = result["TestingCar"]["edges"][0]["node"]

        # Verify name attribute metadata
        assert node["name"]["updated_by"]["id"] == admin_account.id
        assert node["name"]["updated_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert node["name"]["updated_at"] is not None

        # Verify color attribute metadata
        assert node["color"]["updated_by"]["id"] == admin_account.id
        assert node["color"]["updated_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert node["color"]["updated_at"] is not None

    async def test_single_relationship_metadata_created_by_admin(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify relationship_metadata for single relationships (cardinality=ONE).

        For single relationships like owner/manufacturer, the structure is:
        owner { node { ... } relationship_metadata { ... } }
        (no edges array)
        """
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node {
                        id
                        owner {
                            relationship_metadata {
                                created_by {
                                    id
                                    display_label
                                }
                                updated_by {
                                    id
                                    display_label
                                }
                                created_at
                                updated_at
                            }
                            node {
                                id
                                display_label
                            }
                        }
                        manufacturer {
                            relationship_metadata {
                                created_by {
                                    id
                                    display_label
                                }
                                updated_by {
                                    id
                                    display_label
                                }
                            }
                            node {
                                id
                            }
                        }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        assert result["TestingCar"]["edges"]
        node = result["TestingCar"]["edges"][0]["node"]

        # Verify owner relationship metadata (single relationship - no edges)
        owner_rel_metadata = node["owner"]["relationship_metadata"]
        assert owner_rel_metadata["created_by"]["id"] == admin_account.id
        assert owner_rel_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert owner_rel_metadata["updated_by"]["id"] == admin_account.id
        assert owner_rel_metadata["updated_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert owner_rel_metadata["created_at"] is not None
        assert owner_rel_metadata["updated_at"] is not None

        # Verify manufacturer relationship metadata (single relationship - no edges)
        manufacturer_rel_metadata = node["manufacturer"]["relationship_metadata"]
        assert manufacturer_rel_metadata["created_by"]["id"] == admin_account.id
        assert manufacturer_rel_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert manufacturer_rel_metadata["updated_by"]["id"] == admin_account.id
        assert manufacturer_rel_metadata["updated_by"]["display_label"] == initial_dataset["admin_display_label"]

    async def test_many_relationship_metadata_created_by_admin(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify relationship_metadata for many relationships (cardinality=MANY).

        For many relationships like Person.cars, the structure is:
        cars { edges { node { ... } relationship_metadata { ... } } }
        """
        query = """
        query GetPerson($id: ID!) {
            TestingPerson(ids: [$id]) {
                edges {
                    node {
                        id
                        name { value }
                        cars {
                            edges {
                                relationship_metadata {
                                    created_by {
                                        id
                                        display_label
                                    }
                                    updated_by {
                                        id
                                        display_label
                                    }
                                    created_at
                                    updated_at
                                }
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
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["john_id"]})

        assert result["TestingPerson"]["edges"]
        node = result["TestingPerson"]["edges"][0]["node"]
        assert node["name"]["value"] == "John"

        # John should have one car (Jesko)
        car_edges = node["cars"]["edges"]
        assert len(car_edges) == 1
        assert car_edges[0]["node"]["name"]["value"] == "Jesko"

        # Verify relationship metadata (many relationship - has edges)
        rel_metadata = car_edges[0]["relationship_metadata"]
        assert rel_metadata["created_by"]["id"] == admin_account.id
        assert rel_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert rel_metadata["updated_by"]["id"] == admin_account.id
        assert rel_metadata["updated_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert rel_metadata["created_at"] is not None
        assert rel_metadata["updated_at"] is not None

    async def test_attribute_update_changes_updated_by(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
        bot_account: CoreAccount,
    ) -> None:
        """Verify that updating an attribute with bot_client changes updated_by to bot account."""
        # Update the color using bot_client
        car_via_bot = await bot_client.get(kind=TestKind.CAR, id=initial_dataset["jesko_id"])
        car_via_bot.color.value = "Blue"
        await car_via_bot.save()

        # Query the attribute metadata
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node {
                        id
                        color {
                            value
                            updated_by {
                                id
                                display_label
                            }
                            updated_at
                        }
                        name {
                            value
                            updated_by {
                                id
                                display_label
                            }
                        }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        node = result["TestingCar"]["edges"][0]["node"]

        # Verify color attribute was updated by bot
        assert node["color"]["updated_by"]["id"] == bot_account.id
        assert node["color"]["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

        # Verify name attribute was NOT updated (still admin)
        assert node["name"]["updated_by"]["id"] == admin_account.id
        assert node["name"]["updated_by"]["display_label"] == initial_dataset["admin_display_label"]

    async def test_node_metadata_update_changes_updated_by(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
        bot_account: CoreAccount,
    ) -> None:
        """Verify that updating a node with bot_client changes node_metadata updated_by to bot account."""
        # Update the car description using bot_client
        car_via_bot = await bot_client.get(kind=TestKind.CAR, id=initial_dataset["jesko_id"])
        car_via_bot.description.value = "Updated by bot"
        await car_via_bot.save()

        # Query the node metadata
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                        updated_by {
                            id
                            display_label
                        }
                    }
                    node {
                        id
                        description { value }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        node_metadata = result["TestingCar"]["edges"][0]["node_metadata"]

        # Node was created by admin but updated by bot
        assert node_metadata["created_by"]["id"] == admin_account.id
        assert node_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert node_metadata["updated_by"]["id"] == bot_account.id
        assert node_metadata["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

    async def test_single_relationship_update_changes_metadata(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        initial_dataset: dict[str, Any],
        bot_account: CoreAccount,
    ) -> None:
        """Verify that updating a single relationship with bot_client changes relationship_metadata."""
        # Create a new person using admin client
        jane = await client.create(kind=TestKind.PERSON, name="Jane", height=165, description="New owner")
        await jane.save()

        # Update the car's owner using bot_client
        car_via_bot = await bot_client.get(kind=TestKind.CAR, id=initial_dataset["jesko_id"])
        car_via_bot.owner = {"id": jane.id}
        await car_via_bot.save()

        # Query the relationship metadata (single relationship - no edges)
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node {
                        id
                        owner {
                            relationship_metadata {
                                created_by {
                                    id
                                    display_label
                                }
                                updated_by {
                                    id
                                    display_label
                                }
                            }
                            node {
                                id
                                name { value }
                            }
                        }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        owner = result["TestingCar"]["edges"][0]["node"]["owner"]
        assert owner["node"]["name"]["value"] == "Jane"

        # The relationship is new (created by bot) since we changed the owner
        rel_metadata = owner["relationship_metadata"]
        assert rel_metadata["created_by"]["id"] == bot_account.id
        assert rel_metadata["created_by"]["display_label"] == initial_dataset["bot_display_label"]
        assert rel_metadata["updated_by"]["id"] == bot_account.id
        assert rel_metadata["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

    async def test_new_node_created_by_bot(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        initial_dataset: dict[str, Any],
        bot_account: CoreAccount,
    ) -> None:
        """Verify that a new node created by bot_client has bot as created_by."""
        # Create a new car using bot_client
        new_car = await bot_client.create(
            kind=TestKind.CAR,
            name="Regera",
            color="Silver",
            description="A hybrid supercar",
            owner={"id": initial_dataset["john_id"]},
            manufacturer={"id": initial_dataset["koenigsegg_id"]},
        )
        await new_car.save()

        # Query all metadata levels
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                        updated_by {
                            id
                            display_label
                        }
                    }
                    node {
                        id
                        name {
                            value
                            updated_by {
                                id
                                display_label
                            }
                        }
                        owner {
                            relationship_metadata {
                                created_by {
                                    id
                                    display_label
                                }
                                updated_by {
                                    id
                                    display_label
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": new_car.id})

        edges = result["TestingCar"]["edges"]
        assert len(edges) == 1

        # Node metadata: created and updated by bot
        node_metadata = edges[0]["node_metadata"]
        assert node_metadata["created_by"]["id"] == bot_account.id
        assert node_metadata["created_by"]["display_label"] == initial_dataset["bot_display_label"]
        assert node_metadata["updated_by"]["id"] == bot_account.id
        assert node_metadata["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

        # Attribute metadata: updated_by is bot
        assert edges[0]["node"]["name"]["updated_by"]["id"] == bot_account.id
        assert edges[0]["node"]["name"]["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

        # Relationship metadata: created and updated by bot (single relationship - no edges)
        owner_rel_metadata = edges[0]["node"]["owner"]["relationship_metadata"]
        assert owner_rel_metadata["created_by"]["id"] == bot_account.id
        assert owner_rel_metadata["created_by"]["display_label"] == initial_dataset["bot_display_label"]
        assert owner_rel_metadata["updated_by"]["id"] == bot_account.id
        assert owner_rel_metadata["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

    async def test_metadata_timestamps_update(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
    ) -> None:
        """Verify that updated_at timestamps change when updates are made."""
        # Create a new person for this test
        person = await client.create(kind=TestKind.PERSON, name="Timestamp Test", height=180)
        await person.save()

        # Query initial timestamps
        query = """
        query GetPerson($id: ID!) {
            TestingPerson(ids: [$id]) {
                edges {
                    node_metadata {
                        created_at
                        updated_at
                    }
                    node {
                        id
                        name {
                            value
                            updated_at
                        }
                    }
                }
            }
        }
        """
        result1 = await client.execute_graphql(query=query, variables={"id": person.id})

        node_metadata1 = result1["TestingPerson"]["edges"][0]["node_metadata"]
        initial_node_created = node_metadata1["created_at"]
        initial_attr_updated = result1["TestingPerson"]["edges"][0]["node"]["name"]["updated_at"]

        # Update the person's name via bot
        person_via_bot = await bot_client.get(kind=TestKind.PERSON, id=person.id)
        person_via_bot.name.value = "Timestamp Test Updated"
        await person_via_bot.save()

        # Query updated timestamps
        result2 = await client.execute_graphql(query=query, variables={"id": person.id})

        node_metadata2 = result2["TestingPerson"]["edges"][0]["node_metadata"]
        new_attr_updated = result2["TestingPerson"]["edges"][0]["node"]["name"]["updated_at"]

        # created_at should not change
        assert node_metadata2["created_at"] == initial_node_created

        # updated_at should change for modified attribute
        assert new_attr_updated != initial_attr_updated

    async def test_multiple_nodes_batch_metadata(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
        bot_account: CoreAccount,
    ) -> None:
        """Verify metadata is correct when querying multiple nodes created by different accounts."""
        # Create a person with admin
        admin_person = await client.create(kind=TestKind.PERSON, name="Admin Person", height=170)
        await admin_person.save()

        # Create a person with bot
        bot_person = await bot_client.create(kind=TestKind.PERSON, name="Bot Person", height=175)
        await bot_person.save()

        # Query both persons' metadata
        query = """
        query GetPersons($ids: [ID!]) {
            TestingPerson(ids: $ids) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                    }
                    node {
                        id
                        name { value }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"ids": [admin_person.id, bot_person.id]})

        edges = result["TestingPerson"]["edges"]
        assert len(edges) == 2

        # Build a mapping of name -> created_by info
        creator_by_name = {
            edge["node"]["name"]["value"]: {
                "id": edge["node_metadata"]["created_by"]["id"],
                "display_label": edge["node_metadata"]["created_by"]["display_label"],
            }
            for edge in edges
        }

        # Verify correct creators
        assert creator_by_name["Admin Person"]["id"] == admin_account.id
        assert creator_by_name["Admin Person"]["display_label"] == initial_dataset["admin_display_label"]
        assert creator_by_name["Bot Person"]["id"] == bot_account.id
        assert creator_by_name["Bot Person"]["display_label"] == initial_dataset["bot_display_label"]

    async def test_node_metadata_matches_attribute_metadata_after_update(
        self,
        client: InfrahubClient,
        bot_client: InfrahubClient,
        admin_account: CoreAccount,
        bot_account: CoreAccount,
        initial_dataset: dict[str, Any],
    ) -> None:
        """Verify node_metadata updated_at/updated_by match attribute metadata after an attribute update.

        When a node is created, both node_metadata and attribute metadata reflect the creator.
        After an attribute update by a different user, node_metadata should reflect that same
        update - the updated_by and updated_at should match between node_metadata and the
        updated attribute's metadata.
        """
        # Create a fresh node with admin to ensure clean state
        person = await client.create(kind=TestKind.PERSON, name="Fresh Person", height=180, description="Test person")
        await person.save()

        # Query initial state - both node and attribute metadata should show admin
        query = """
        query GetPerson($id: ID!) {
            TestingPerson(ids: [$id]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                        updated_by {
                            id
                            display_label
                        }
                        created_at
                        updated_at
                    }
                    node {
                        id
                        name {
                            value
                            updated_by {
                                id
                                display_label
                            }
                            updated_at
                        }
                        height {
                            value
                            updated_by {
                                id
                                display_label
                            }
                            updated_at
                        }
                    }
                }
            }
        }
        """
        result_initial = await client.execute_graphql(query=query, variables={"id": person.id})

        initial_node_metadata = result_initial["TestingPerson"]["edges"][0]["node_metadata"]
        initial_node = result_initial["TestingPerson"]["edges"][0]["node"]

        # Verify initial state: all metadata points to admin
        assert initial_node_metadata["created_by"]["id"] == admin_account.id
        assert initial_node_metadata["updated_by"]["id"] == admin_account.id
        assert initial_node["name"]["updated_by"]["id"] == admin_account.id
        assert initial_node["height"]["updated_by"]["id"] == admin_account.id

        # Now update only the height attribute using bot_client
        person_via_bot = await bot_client.get(kind=TestKind.PERSON, id=person.id)
        person_via_bot.height.value = 185
        await person_via_bot.save()

        # Query after update
        result_after = await client.execute_graphql(query=query, variables={"id": person.id})

        after_node_metadata = result_after["TestingPerson"]["edges"][0]["node_metadata"]
        after_node = result_after["TestingPerson"]["edges"][0]["node"]

        # node_metadata.created_by should still be admin (creator doesn't change)
        assert after_node_metadata["created_by"]["id"] == admin_account.id
        assert after_node_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]

        # node_metadata.updated_by should now be bot (reflects the latest update)
        assert after_node_metadata["updated_by"]["id"] == bot_account.id
        assert after_node_metadata["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

        # The updated height attribute should show bot as updated_by
        assert after_node["height"]["updated_by"]["id"] == bot_account.id
        assert after_node["height"]["updated_by"]["display_label"] == initial_dataset["bot_display_label"]

        # The unchanged name attribute should still show admin as updated_by
        assert after_node["name"]["updated_by"]["id"] == admin_account.id
        assert after_node["name"]["updated_by"]["display_label"] == initial_dataset["admin_display_label"]

        # KEY ASSERTION: node_metadata.updated_at should match the height attribute's updated_at
        # since height was the most recently updated attribute
        assert after_node_metadata["updated_at"] == after_node["height"]["updated_at"]

        # node_metadata.updated_at should be different from the unchanged name attribute's updated_at
        # (unless they happen to be the same due to timing, which is unlikely)
        # More importantly, it should NOT be the old created_at value
        assert after_node_metadata["updated_at"] != initial_node_metadata["created_at"]

    async def test_metadata_with_typename(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify __typename is returned correctly for account in metadata."""
        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node_metadata {
                        created_by {
                            __typename
                            id
                            display_label
                        }
                        updated_by {
                            __typename
                            id
                            display_label
                        }
                    }
                    node {
                        id
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset["jesko_id"]})

        node_metadata = result["TestingCar"]["edges"][0]["node_metadata"]

        # Verify __typename is CoreAccount
        assert node_metadata["created_by"]["__typename"] == "CoreAccount"
        assert node_metadata["updated_by"]["__typename"] == "CoreAccount"

        # Also verify display_label is present
        assert node_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert node_metadata["updated_by"]["display_label"] is not None

    async def test_same_account_different_fields_in_same_query(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify that the same account can be queried with different field sets in the same query.

        This tests the AccountDataLoader's behavior when:
        1. node_metadata.created_by requests: id, display_label
        2. node_metadata.updated_by requests: id, name { value } (an actual attribute)
        3. name.updated_by requests: id only
        4. color.updated_by requests: id, display_label, name { value }, __typename (all fields)

        The concern: DataLoader caches by key (account ID). If two parts of the query
        request the same account with different fields, the cached result from the
        first resolution might not have all fields needed by subsequent resolutions.

        This test verifies that each resolution point gets the fields it requests,
        including nested attribute fields like `name { value }` that require actual
        database queries.

        How it works: The AccountMetadataResolver creates loaders keyed by
        AccountLoaderParams (branch + timestamp). Within each resolution, the resolver
        calls loader.load(account_id) which returns the cached result. GraphQL then
        picks the requested fields from that result. Since the loader's batch_load_fn
        fetches accounts with the fields from the FIRST request that creates the loader,
        subsequent requests for the same account get that same data. GraphQL resolvers
        then return only the fields requested in the query selection set.
        """
        fresh_car = await client.create(
            kind=TestKind.CAR,
            name="FieldTest",
            color="Green",
            description="A car for testing field selection",
            owner={"id": initial_dataset["john_id"]},
            manufacturer={"id": initial_dataset["koenigsegg_id"]},
        )
        await fresh_car.save()

        query = """
        query GetCar($id: ID!) {
            TestingCar(ids: [$id]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                        updated_by {
                            id
                            name {
                                value
                            }
                        }
                    }
                    node {
                        id
                        name {
                            value
                            updated_by {
                                id
                            }
                        }
                        color {
                            value
                            updated_by {
                                id
                                display_label
                                name {
                                    value
                                }
                                __typename
                            }
                        }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": fresh_car.id})

        edge = result["TestingCar"]["edges"][0]
        node_metadata = edge["node_metadata"]
        node = edge["node"]

        # Verify created_by has id and display_label, but NOT name
        assert node_metadata["created_by"]["id"] == admin_account.id
        assert node_metadata["created_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert "name" not in node_metadata["created_by"]
        assert "__typename" not in node_metadata["created_by"]

        # Verify updated_by has id and name { value }, but NOT display_label
        assert node_metadata["updated_by"]["id"] == admin_account.id
        assert node_metadata["updated_by"]["name"]["value"] == "admin"
        assert "display_label" not in node_metadata["updated_by"]
        assert "__typename" not in node_metadata["updated_by"]

        # Verify name.updated_by has only id
        assert node["name"]["updated_by"]["id"] == admin_account.id
        assert "display_label" not in node["name"]["updated_by"]
        assert "name" not in node["name"]["updated_by"]
        assert "__typename" not in node["name"]["updated_by"]

        # Verify color.updated_by has all requested fields including name { value }
        assert node["color"]["updated_by"]["id"] == admin_account.id
        assert node["color"]["updated_by"]["display_label"] == initial_dataset["admin_display_label"]
        assert node["color"]["updated_by"]["name"]["value"] == "admin"
        assert node["color"]["updated_by"]["__typename"] == "CoreAccount"

    async def test_multiple_nodes_same_creator_different_field_requests(
        self,
        client: InfrahubClient,
        initial_dataset: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        """Verify correct behavior when querying multiple nodes created by the same account.

        This tests a scenario where the AccountDataLoader's batching and caching
        is exercised across multiple nodes that share the same creator:
        - Node 1's created_by requests: id, display_label
        - Node 2's created_by requests: id, name { value }

        Both should get their requested fields correctly, even though they request
        different fields for the same underlying account.
        """
        # Query both the car and the person (both created by admin)
        query = """
        query GetData($carId: ID!, $personId: ID!) {
            TestingCar(ids: [$carId]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            display_label
                        }
                    }
                    node {
                        id
                        name { value }
                    }
                }
            }
            TestingPerson(ids: [$personId]) {
                edges {
                    node_metadata {
                        created_by {
                            id
                            name {
                                value
                            }
                        }
                    }
                    node {
                        id
                        name { value }
                    }
                }
            }
        }
        """
        result = await client.execute_graphql(
            query=query,
            variables={
                "carId": initial_dataset["jesko_id"],
                "personId": initial_dataset["john_id"],
            },
        )

        car_created_by = result["TestingCar"]["edges"][0]["node_metadata"]["created_by"]
        person_created_by = result["TestingPerson"]["edges"][0]["node_metadata"]["created_by"]

        # Both should have the same admin account ID
        assert car_created_by["id"] == admin_account.id
        assert person_created_by["id"] == admin_account.id

        # Car's created_by should have display_label but not name
        assert car_created_by["display_label"] == initial_dataset["admin_display_label"]
        assert "name" not in car_created_by

        # Person's created_by should have name { value } but not display_label
        assert person_created_by["name"]["value"] == "admin"
        assert "display_label" not in person_created_by

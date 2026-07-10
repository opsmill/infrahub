"""Verify that removing a relationship from a schema closes its data on the node and on its
profile and object-template copies, and that re-adding the same relationship does not resurface the
closed data.

Flow:
  step01 - load schema with a relationship, create node/profile/template data, verify data is active
  step02 - remove the relationship, verify the node/profile/template relationship data is closed
  step03 - re-add the relationship and set a new peer, verify the closed data does not resurface
"""

from copy import deepcopy
from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

WIDGET_KIND = "TestingWidget"
GIZMO_KIND = "TestingGizmo"
PROFILE_WIDGET_KIND = "ProfileTestingWidget"
TEMPLATE_WIDGET_KIND = "TemplateTestingWidget"


LINK_KIND = "TestingLink"
HUB_KIND = "TestingHub"
SHARED_IDENTIFIER = "link_hub_shared"


async def _count_active_is_related(db: InfrahubDatabase, identifier: str) -> int:
    query = """
    MATCH (n:Node)-[r:IS_RELATED]-(rel:Relationship {name: $identifier})
    WHERE r.status = "active" AND r.to IS NULL
    RETURN count(r) AS nbr
    """
    results = await db.execute_query(query=query, params={"identifier": identifier})
    return results[0]["nbr"]


class TestSchemaRelationshipRemoveAdd(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_widget_base(self) -> dict[str, Any]:
        return {
            "name": "Widget",
            "namespace": "Testing",
            "generate_template": True,
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                # default kind is Generic -> replicated onto both profile and template copies
                {"name": "gizmo", "peer": GIZMO_KIND, "cardinality": "one", "optional": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_gizmo(self) -> dict[str, Any]:
        return {
            "name": "Gizmo",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        }

    @pytest.fixture(scope="class")
    def schema_step_01(self, schema_widget_base: dict[str, Any], schema_gizmo: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_widget_base, schema_gizmo]}

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_widget_base: dict[str, Any], schema_gizmo: dict[str, Any]) -> dict[str, Any]:
        widget = deepcopy(schema_widget_base)
        for relationship in widget["relationships"]:
            if relationship["name"] == "gizmo":
                relationship["state"] = "absent"
        return {"version": "1.0", "nodes": [widget, schema_gizmo]}

    @pytest.fixture(scope="class")
    def schema_step_03(self, schema_step_01: dict[str, Any]) -> dict[str, Any]:
        """Re-add the relationship by loading the original schema again."""
        return deepcopy(schema_step_01)

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step_01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        gizmo = await Node.init(schema=GIZMO_KIND, db=db)
        await gizmo.new(db=db, name="gizmo-1")
        await gizmo.save(db=db)

        widget = await Node.init(schema=WIDGET_KIND, db=db)
        await widget.new(db=db, name="widget-1", gizmo=gizmo)
        await widget.save(db=db)

        profile = await Node.init(schema=PROFILE_WIDGET_KIND, db=db)
        await profile.new(db=db, profile_name="widget-profile", gizmo=gizmo)
        await profile.save(db=db)

        template = await Node.init(schema=TEMPLATE_WIDGET_KIND, db=db)
        await template.new(db=db, template_name="widget-template", gizmo=gizmo)
        await template.save(db=db)

        base_identifier = registry.schema.get_node_schema(name=WIDGET_KIND).get_relationship("gizmo").get_identifier()
        return {
            "gizmo": gizmo.id,
            "widget": widget.id,
            "profile": profile.id,
            "template": template.id,
            "base_identifier": base_identifier,
            "profile_identifier": f"profile_{base_identifier}",
            "template_identifier": f"template_{base_identifier}",
        }

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        """The relationship data is active on the node, the profile and the template."""
        assert await _count_active_is_related(db=db, identifier=initial_dataset["base_identifier"]) == 2
        assert await _count_active_is_related(db=db, identifier=initial_dataset["profile_identifier"]) == 2
        assert await _count_active_is_related(db=db, identifier=initial_dataset["template_identifier"]) == 2

    async def test_step02_remove_relationship(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_02: dict[str, Any],
    ) -> None:
        """Removing the relationship closes its data on the node, the profile and the template."""
        response = await client.schema.load(schemas=[schema_step_02])
        assert not response.errors

        assert "gizmo" not in registry.schema.get_node_schema(name=WIDGET_KIND).relationship_names

        assert await _count_active_is_related(db=db, identifier=initial_dataset["base_identifier"]) == 0
        assert await _count_active_is_related(db=db, identifier=initial_dataset["profile_identifier"]) == 0
        assert await _count_active_is_related(db=db, identifier=initial_dataset["template_identifier"]) == 0

        await verify_graph(db=db)

    async def test_step03_readd_no_resurface(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_03: dict[str, Any],
    ) -> None:
        """Re-adding the relationship must not resurface the previously closed data."""
        response = await client.schema.load(schemas=[schema_step_03])
        assert not response.errors
        assert "gizmo" in registry.schema.get_node_schema(name=WIDGET_KIND).relationship_names

        # Re-adding the relationship must not resurface the widget's previously closed peer
        widget = await NodeManager.get_one(db=db, id=initial_dataset["widget"])
        assert widget is not None
        assert await widget.get_relationship("gizmo").get_peer(db=db) is None

        # Assign a new peer on the node and confirm only it is reachable
        new_gizmo = await Node.init(schema=GIZMO_KIND, db=db)
        await new_gizmo.new(db=db, name="gizmo-2")
        await new_gizmo.save(db=db)

        await widget.get_relationship("gizmo").update(db=db, data=new_gizmo)
        await widget.save(db=db)

        reloaded_widget = await NodeManager.get_one(db=db, id=initial_dataset["widget"])
        assert reloaded_widget is not None
        widget_peer = await reloaded_widget.get_relationship("gizmo").get_peer(db=db)
        assert widget_peer is not None
        assert widget_peer.get_id() == new_gizmo.id

        # The profile and template kept no gizmo, so their previously closed data must not resurface
        profile = await NodeManager.get_one(db=db, id=initial_dataset["profile"])
        assert profile is not None
        assert await profile.get_relationship("gizmo").get_peer(db=db) is None

        template = await NodeManager.get_one(db=db, id=initial_dataset["template"])
        assert template is not None
        assert await template.get_relationship("gizmo").get_peer(db=db) is None

        # Only the new node->gizmo relationship is active; the profile/template identifiers stay closed
        assert await _count_active_is_related(db=db, identifier=initial_dataset["base_identifier"]) == 2
        assert await _count_active_is_related(db=db, identifier=initial_dataset["profile_identifier"]) == 0
        assert await _count_active_is_related(db=db, identifier=initial_dataset["template_identifier"]) == 0

        await verify_graph(db=db)


class TestSchemaRelationshipRemoveInversePair(TestInfrahubApp):
    """An inbound/outbound relationship pair sharing an identifier shares the same graph data.

    Removing one side must be a no-op (the surviving side keeps the data alive); the data is only
    closed once both sides are removed from the schema.
    """

    @pytest.fixture(scope="class")
    def schema_link(self) -> dict[str, Any]:
        return {
            "name": "Link",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                {
                    "name": "hub",
                    "peer": HUB_KIND,
                    "cardinality": "one",
                    "optional": True,
                    "direction": "outbound",
                    "identifier": SHARED_IDENTIFIER,
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_hub(self) -> dict[str, Any]:
        return {
            "name": "Hub",
            "namespace": "Testing",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                {
                    "name": "links",
                    "peer": LINK_KIND,
                    "cardinality": "many",
                    "optional": True,
                    "direction": "inbound",
                    "identifier": SHARED_IDENTIFIER,
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step_01(self, schema_link: dict[str, Any], schema_hub: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_link, schema_hub]}

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_link: dict[str, Any], schema_hub: dict[str, Any]) -> dict[str, Any]:
        """Remove only the outbound side (Link.hub); the inbound side (Hub.links) survives."""
        link = deepcopy(schema_link)
        link["relationships"][0]["state"] = "absent"
        return {"version": "1.0", "nodes": [link, schema_hub]}

    @pytest.fixture(scope="class")
    def schema_step_03(self, schema_link: dict[str, Any], schema_hub: dict[str, Any]) -> dict[str, Any]:
        """Remove the inbound side too; now no schema references the identifier."""
        link = deepcopy(schema_link)
        link["relationships"][0]["state"] = "absent"
        hub = deepcopy(schema_hub)
        hub["relationships"][0]["state"] = "absent"
        return {"version": "1.0", "nodes": [link, hub]}

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step_01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        hub = await Node.init(schema=HUB_KIND, db=db)
        await hub.new(db=db, name="hub-1")
        await hub.save(db=db)

        link = await Node.init(schema=LINK_KIND, db=db)
        await link.new(db=db, name="link-1", hub=hub)
        await link.save(db=db)

        return {"hub": hub.id, "link": link.id}

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        """The shared relationship data is active (one vertex, two IS_RELATED edges)."""
        assert await _count_active_is_related(db=db, identifier=SHARED_IDENTIFIER) == 2

    async def test_step02_remove_one_side_is_noop(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_02: dict[str, Any],
    ) -> None:
        """Removing only Link.hub leaves the data intact because Hub.links still references it."""
        response = await client.schema.load(schemas=[schema_step_02])
        assert not response.errors

        assert "hub" not in registry.schema.get_node_schema(name=LINK_KIND).relationship_names
        assert "links" in registry.schema.get_node_schema(name=HUB_KIND).relationship_names

        # Data is untouched and still reachable from the surviving side
        assert await _count_active_is_related(db=db, identifier=SHARED_IDENTIFIER) == 2
        hub = await NodeManager.get_one(db=db, id=initial_dataset["hub"])
        assert hub is not None
        assert {peer.get_id() for peer in (await hub.get_relationship("links").get_peers(db=db)).values()} == {
            initial_dataset["link"]
        }

        await verify_graph(db=db)

    async def test_step03_remove_both_sides_closes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_03: dict[str, Any],
    ) -> None:
        """Removing the second side closes the shared relationship data."""
        response = await client.schema.load(schemas=[schema_step_03])
        assert not response.errors

        assert "links" not in registry.schema.get_node_schema(name=HUB_KIND).relationship_names
        assert await _count_active_is_related(db=db, identifier=SHARED_IDENTIFIER) == 0

        await verify_graph(db=db)


ANIMAL_GENERIC = "TestingAnimal"
DOG_KIND = "TestingDog"
CAT_KIND = "TestingCat"
KEEPER_KIND = "TestingKeeper"
KEEPER_IDENTIFIER = "animal_keeper"


class TestSchemaRelationshipRemoveGenericOverride(TestInfrahubApp):
    """Removing a relationship from a generic closes the inherited data, but an inheriting kind that

    overrides the relationship (keeping the same identifier) keeps its own data.
    """

    @pytest.fixture(scope="class")
    def keeper_relationship(self) -> dict[str, Any]:
        return {
            "name": "keeper",
            "peer": KEEPER_KIND,
            "cardinality": "one",
            "optional": True,
            "identifier": KEEPER_IDENTIFIER,
        }

    @pytest.fixture(scope="class")
    def schema_step_01(self, keeper_relationship: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [
                {
                    "name": "Animal",
                    "namespace": "Testing",
                    "attributes": [{"name": "name", "kind": "Text", "unique": True}],
                    "relationships": [deepcopy(keeper_relationship)],
                },
            ],
            "nodes": [
                {"name": "Keeper", "namespace": "Testing", "attributes": [{"name": "name", "kind": "Text"}]},
                {"name": "Dog", "namespace": "Testing", "inherit_from": [ANIMAL_GENERIC]},
                {
                    "name": "Cat",
                    "namespace": "Testing",
                    "inherit_from": [ANIMAL_GENERIC],
                    "relationships": [deepcopy(keeper_relationship)],
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_step_01: dict[str, Any]) -> dict[str, Any]:
        """Remove ``keeper`` from the generic; Cat keeps its own override."""
        schema = deepcopy(schema_step_01)
        schema["generics"][0]["relationships"][0]["state"] = "absent"
        return schema

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step_01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        keeper = await Node.init(schema=KEEPER_KIND, db=db)
        await keeper.new(db=db, name="keeper-1")
        await keeper.save(db=db)

        dog = await Node.init(schema=DOG_KIND, db=db)
        await dog.new(db=db, name="dog-1", keeper=keeper)
        await dog.save(db=db)

        cat = await Node.init(schema=CAT_KIND, db=db)
        await cat.new(db=db, name="cat-1", keeper=keeper)
        await cat.save(db=db)

        return {"keeper": keeper.id, "dog": dog.id, "cat": cat.id}

    async def test_step01_baseline(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        """Both the Dog (inherited) and the Cat (override) keeper data are active."""
        # 2 Relationship vertices (dog-keeper, cat-keeper), 2 IS_RELATED edges each
        assert await _count_active_is_related(db=db, identifier=KEEPER_IDENTIFIER) == 4

    async def test_step02_remove_from_generic_keeps_override(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_02: dict[str, Any],
    ) -> None:
        """The inherited Dog data is closed; the Cat override keeps its data."""
        response = await client.schema.load(schemas=[schema_step_02])
        assert not response.errors

        assert "keeper" not in registry.schema.get_generic_schema(name=ANIMAL_GENERIC).relationship_names
        assert "keeper" not in registry.schema.get_node_schema(name=DOG_KIND).relationship_names
        assert "keeper" in registry.schema.get_node_schema(name=CAT_KIND).relationship_names

        # Only the Cat override data remains active
        assert await _count_active_is_related(db=db, identifier=KEEPER_IDENTIFIER) == 2

        cat = await NodeManager.get_one(db=db, id=initial_dataset["cat"])
        assert cat is not None
        cat_peer = await cat.get_relationship("keeper").get_peer(db=db)
        assert cat_peer is not None
        assert cat_peer.get_id() == initial_dataset["keeper"]

        await verify_graph(db=db)

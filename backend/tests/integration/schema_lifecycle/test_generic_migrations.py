from random import randint
from typing import Any

import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship.model import RelationshipManager
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.helpers.db_validation import validate_no_duplicate_attributes

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

GENERIC_KIND = "TestingGeneric"
SPECIFIC_ONE_KIND = "TestingSpecificOne"
SPECIFIC_TWO_KIND = "TestingSpecificTwo"
SPECIFIC_THREE_KIND = "TestingSpecificThree"
THING_KIND = "TestingThing"


class SchemaLifecycleGenericBase(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    def schema_thing(self) -> dict[str, Any]:
        return {
            "name": "Thing",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Thing",
            "attributes": [
                {"name": "value", "kind": "Text"},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_generic_base(self) -> dict[str, Any]:
        return {
            "name": "Generic",
            "namespace": "Testing",
            "attributes": [
                {"name": "generic_attr_text", "kind": "Text", "optional": True, "order_weight": 1111},
                {"name": "generic_attr_num", "kind": "Number", "optional": True, "order_weight": 2222},
                {"name": "generic_required_attr", "kind": "Text", "optional": False},
            ],
            "relationships": [
                {
                    "name": "things",
                    "identifier": "generic__things",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingThing",
                    "cardinality": "many",
                    "order_weight": 3333,
                },
                {
                    "name": "favorite_thing",
                    "identifier": "generic__favoritething",
                    "kind": "Generic",
                    "optional": True,
                    "peer": "TestingThing",
                    "cardinality": "one",
                    "order_weight": 4444,
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_specific_one_base(self) -> dict[str, Any]:
        return {
            "name": "SpecificOne",
            "namespace": "Testing",
            "inherit_from": ["TestingGeneric"],
        }

    @pytest.fixture(scope="class")
    def schema_specific_two_base(self) -> dict[str, Any]:
        return {
            "name": "SpecificTwo",
            "namespace": "Testing",
            "inherit_from": ["TestingGeneric"],
        }

    @pytest.fixture(scope="class")
    def schema_specific_three_base(self) -> dict[str, Any]:
        return {
            "name": "SpecificThree",
            "namespace": "Testing",
            "inherit_from": ["TestingGeneric"],
            "attributes": [{"name": "generic_required_attr", "kind": "Text", "optional": True}],
        }

    @pytest.fixture(scope="class")
    def schema_step_01(
        self,
        schema_generic_base,
        schema_specific_one_base,
        schema_specific_two_base,
        schema_specific_three_base,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_base],
            "nodes": [schema_specific_one_base, schema_specific_two_base, schema_specific_three_base, schema_thing],
        }

    @pytest.fixture(scope="class")
    async def branch_name(self) -> str:
        num = randint(1000, 9999)
        return f"branch-{num}"

    @pytest.fixture(scope="class")
    async def initial_objects(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initialize_registry,
        schema_step_01,
    ) -> dict[str, Node]:
        await load_schema(db=db, schema=schema_step_01)

        thing_one = await Node.init(schema=THING_KIND, db=db)
        await thing_one.new(db=db, value="ONE")
        await thing_one.save(db=db)

        thing_two = await Node.init(schema=THING_KIND, db=db)
        await thing_two.new(db=db, value="TWO")
        await thing_two.save(db=db)

        thing_three = await Node.init(schema=THING_KIND, db=db)
        await thing_three.new(db=db, value="THREE")
        await thing_three.save(db=db)

        specific_one = await Node.init(schema=SPECIFIC_ONE_KIND, db=db)
        await specific_one.new(
            db=db,
            generic_attr_text="Alpha",
            generic_attr_num=1,
            generic_required_attr="required",
            favorite_thing=thing_one,
        )
        await specific_one.save(db=db)

        deleted_specific_one = await Node.init(schema=SPECIFIC_ONE_KIND, db=db)
        await deleted_specific_one.new(
            db=db,
            generic_attr_text="Deleted-Alpha",
            generic_attr_num=-1,
            generic_required_attr="required",
            favorite_thing=thing_one,
        )
        await deleted_specific_one.save(db=db)
        await deleted_specific_one.delete(db=db)

        specific_two = await Node.init(schema=SPECIFIC_TWO_KIND, db=db)
        await specific_two.new(
            db=db,
            generic_attr_text="Bravo",
            generic_attr_num=2,
            generic_required_attr="required",
            favorite_thing=thing_two,
        )
        await specific_two.save(db=db)

        deleted_specific_two = await Node.init(schema=SPECIFIC_TWO_KIND, db=db)
        await deleted_specific_two.new(
            db=db,
            generic_attr_text="Deleted-Bravo",
            generic_attr_num=-2,
            generic_required_attr="required",
            favorite_thing=thing_two,
        )
        await deleted_specific_two.save(db=db)
        await deleted_specific_two.delete(db=db)

        specific_three = await Node.init(schema=SPECIFIC_THREE_KIND, db=db)
        await specific_three.new(db=db, generic_attr_text="Charlie", generic_attr_num=3, favorite_thing=thing_three)
        await specific_three.save(db=db)

        deleted_specific_three = await Node.init(schema=SPECIFIC_THREE_KIND, db=db)
        await deleted_specific_three.new(
            db=db, generic_attr_text="Deleted-Charlie", generic_attr_num=-3, favorite_thing=thing_three
        )
        await deleted_specific_three.save(db=db)
        await deleted_specific_three.delete(db=db)

        objs = {
            "thing_one": thing_one,
            "thing_two": thing_two,
            "thing_three": thing_three,
            "specific_one": specific_one,
            "specific_two": specific_two,
            "specific_three": specific_three,
        }
        return objs

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_objects: dict[str, Node],
        client: InfrahubClient,
        branch_name: str,
    ) -> dict[str, Node]:
        await client.branch.create(branch_name=branch_name, wait_until_completion=True)
        return initial_objects

    @pytest.fixture(params=[True, False])
    async def branch(self, request, db: InfrahubDatabase, default_branch: Branch, branch_name: str) -> Branch:
        if request.param:
            return default_branch
        return await registry.get_branch(db=db, branch=branch_name)

    @pytest.fixture(scope="class")
    def schema_generic_with_new_fields(self, schema_generic_base: dict[str, Any]) -> dict[str, Any]:
        schema_dict = schema_generic_base.copy()
        schema_dict["attributes"].append(
            {"name": "generic_attr_text_new", "kind": "Text", "optional": True},
        )
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_specific_one_with_overrides(self, schema_specific_one_base: dict[str, Any]) -> dict[str, Any]:
        schema_dict = schema_specific_one_base.copy()
        schema_dict["attributes"] = [
            {
                "name": "generic_attr_text",
                "kind": "Text",
                "optional": True,
                "default_value": "this default",
                "order_weight": 1011,
            },
            {
                "name": "generic_required_attr",
                "kind": "Text",
                "optional": True,
            },
        ]
        schema_dict["relationships"] = [
            {
                "name": "things",
                "identifier": "generic__things",
                "kind": "Generic",
                "optional": True,
                "peer": "TestingThing",
                "cardinality": "many",
                "max_count": 3,
                "order_weight": 3011,
            },
        ]
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_specific_two_with_new_fields(self, schema_specific_two_base: dict[str, Any]) -> dict[str, Any]:
        schema_dict = schema_specific_two_base.copy()
        schema_dict["attributes"] = [
            {"name": "specific_attr_text", "kind": "Text", "optional": True, "default_value": "this default"},
        ]
        schema_dict["relationships"] = [
            {
                "name": "specific_things",
                "identifier": "specific__things",
                "kind": "Generic",
                "optional": True,
                "peer": "TestingThing",
                "cardinality": "many",
            },
        ]
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_specific_three_with_overrides(self, schema_specific_three_base: dict[str, Any]) -> dict[str, Any]:
        schema_dict = schema_specific_three_base.copy()
        schema_dict["attributes"] = [
            {
                "name": "generic_attr_text",
                "kind": "Text",
                "optional": True,
                "regex": "^[A-Z][a-z]+",
                "order_weight": 1033,
            },
            {"name": "specific_attr_num", "kind": "Number", "optional": True},
        ]
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_step_02(
        self,
        schema_generic_with_new_fields,
        schema_specific_one_with_overrides,
        schema_specific_two_with_new_fields,
        schema_specific_three_with_overrides,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_with_new_fields],
            "nodes": [
                schema_specific_one_with_overrides,
                schema_specific_two_with_new_fields,
                schema_specific_three_with_overrides,
                schema_thing,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_specific_three_with_deleted_override(
        self, schema_specific_three_with_overrides: dict[str, Any]
    ) -> dict[str, Any]:
        schema_dict = schema_specific_three_with_overrides.copy()
        schema_dict["attributes"][0]["state"] = "absent"
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_step_03(
        self,
        schema_specific_one_with_overrides,
        schema_specific_two_with_new_fields,
        schema_specific_three_with_deleted_override,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [
                schema_specific_one_with_overrides,
                schema_specific_two_with_new_fields,
                schema_specific_three_with_deleted_override,
                schema_thing,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_generic_with_weight_updates(
        self, db: InfrahubDatabase, schema_generic_with_new_fields: dict[str, Any]
    ) -> dict[str, Any]:
        schema_dict = schema_generic_with_new_fields.copy()
        for attr in schema_dict["attributes"]:
            if "order_weight" in attr:
                attr["order_weight"] += 1
        for rel in schema_dict["relationships"]:
            if "order_weight" in rel:
                rel["order_weight"] += 1
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_step_04(
        self,
        schema_generic_with_weight_updates,
        schema_specific_one_with_overrides,
        schema_specific_two_with_new_fields,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_with_weight_updates],
            "nodes": [
                schema_specific_one_with_overrides,
                schema_specific_two_with_new_fields,
                schema_thing,
            ],
        }

    @pytest.fixture(scope="class")
    def schema_generic_with_deletes(
        self, db: InfrahubDatabase, schema_generic_with_weight_updates: dict[str, Any]
    ) -> dict[str, Any]:
        schema_dict = schema_generic_with_weight_updates.copy()
        for attr in schema_dict["attributes"]:
            if attr["name"] in ("generic_attr_text", "generic_required_attr"):
                attr["state"] = HashableModelState.ABSENT.value
        for rel in schema_dict["relationships"]:
            if rel["name"] == "things":
                rel["state"] = HashableModelState.ABSENT.value
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_step_05(
        self,
        schema_generic_with_deletes,
        schema_specific_one_with_overrides,
        schema_specific_two_with_new_fields,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_with_deletes],
            "nodes": [schema_specific_one_with_overrides, schema_specific_two_with_new_fields, schema_thing],
        }

    @pytest.fixture(scope="class")
    def schema_generic_without_deleted_fields(
        self, db: InfrahubDatabase, schema_generic_with_weight_updates: dict[str, Any]
    ) -> dict[str, Any]:
        schema_dict = schema_generic_with_weight_updates.copy()
        schema_dict["attributes"] = [
            a for a in schema_dict["attributes"] if a["name"] not in ("generic_attr_text", "generic_required_attr")
        ]
        schema_dict["relationships"] = [r for r in schema_dict["relationships"] if r["name"] != "things"]
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_specific_one_with_deleted_overrides(
        self, schema_specific_one_with_overrides: dict[str, Any]
    ) -> dict[str, Any]:
        schema_dict = schema_specific_one_with_overrides.copy()
        for attr in schema_dict["attributes"]:
            if attr["name"] == "generic_attr_text":
                attr["state"] = HashableModelState.ABSENT.value
        for rel in schema_dict["relationships"]:
            if rel["name"] == "things":
                rel["state"] = HashableModelState.ABSENT.value
        return schema_dict

    @pytest.fixture(scope="class")
    def schema_step_06(
        self,
        schema_generic_without_deleted_fields,
        schema_specific_one_with_deleted_overrides,
        schema_specific_two_with_new_fields,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_without_deleted_fields],
            "nodes": [schema_specific_one_with_deleted_overrides, schema_specific_two_with_new_fields, schema_thing],
        }

    async def _refresh_registry(self, db: InfrahubDatabase, branch: Branch) -> None:
        current_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        registry.schema.set_schema_branch(name=branch.name, schema=current_schema_branch)

    async def validate_database(
        self, db: InfrahubDatabase, branch: Branch, inheriting_schemas: list[NodeSchema]
    ) -> list[str]:
        return []

    async def test_step01_baseline_backend(
        self, db: InfrahubDatabase, branch: Branch, client: InfrahubClient, initial_dataset
    ):
        all_specifics = await registry.manager.query(db=db, schema=GENERIC_KIND)
        assert len(all_specifics) == 3

        # verify create and delete using the client
        node = await client.create(
            kind=SPECIFIC_THREE_KIND,
            branch=branch.name,
            data={
                "generic_attr_text": "David",
                "generic_attr_num": 4,
                # no generic_required_attr set
                "favorite_thing": initial_dataset["thing_three"].id,
            },
        )
        await node.save()
        retrieved_node = await client.get(kind=SPECIFIC_THREE_KIND, branch=branch.name, id=node.id)
        assert retrieved_node.generic_attr_text.value == "David"
        assert retrieved_node.generic_attr_num.value == 4
        assert retrieved_node.generic_required_attr.value is None
        await node.delete()

        errors = await self.validate_database(
            db=db,
            branch=branch,
            inheriting_schemas=[
                db.schema.get_node_schema(name=schema_kind, branch=branch, duplicate=False)
                for schema_kind in (SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND)
            ],
        )
        assert not errors

    async def test_step02_check_add_specific_overrides(
        self,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_02: dict[str, Any],
    ):
        success, response = await client.schema.check(schemas=[schema_step_02], branch=branch.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    GENERIC_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {
                                    "generic_attr_text_new": None,
                                },
                                "changed": {},
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    SPECIFIC_ONE_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {
                                    "generic_attr_text_new": None,
                                },
                                "changed": {
                                    "generic_attr_text": {
                                        "added": {},
                                        "changed": {
                                            "order_weight": None,
                                            "default_value": None,
                                            "inherited": None,
                                        },
                                        "removed": {},
                                    },
                                    "generic_required_attr": {
                                        "added": {},
                                        "changed": {
                                            "inherited": None,
                                            "optional": None,
                                        },
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "things": {
                                        "added": {},
                                        "changed": {
                                            "order_weight": None,
                                            "max_count": None,
                                            "inherited": None,
                                        },
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    SPECIFIC_TWO_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {
                                    "specific_attr_text": None,
                                    "generic_attr_text_new": None,
                                },
                                "changed": {},
                                "removed": {},
                            },
                            "relationships": {
                                "added": {
                                    "specific_things": None,
                                },
                                "changed": {},
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    SPECIFIC_THREE_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {
                                    "specific_attr_num": None,
                                    "generic_attr_text_new": None,
                                },
                                "changed": {
                                    "generic_attr_text": {
                                        "added": {},
                                        "changed": {
                                            "parameters": {"added": {}, "changed": {"regex": None}, "removed": {}},
                                            "regex": None,
                                            "inherited": None,
                                            "order_weight": None,
                                        },
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step02_load_schema_with_overrides(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_02: dict[str, Any],
    ):
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_02], branch=branch.name)
        assert not response.errors

        await self._refresh_registry(db=db, branch=branch)
        retrieved_specific_one = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_one"].id)
        assert retrieved_specific_one.generic_attr_text.value == "Alpha"
        assert retrieved_specific_one.generic_attr_num.value == 1
        assert retrieved_specific_one.generic_required_attr.value == "required"
        rels_one = await retrieved_specific_one.favorite_thing.get_relationships(db=db)
        assert len(rels_one) == 1
        assert rels_one[0].peer_id == initial_dataset["thing_one"].id
        assert isinstance(retrieved_specific_one.things, RelationshipManager)

        retrieved_specific_two = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_two"].id)
        assert retrieved_specific_two.generic_attr_text.value == "Bravo"
        assert retrieved_specific_two.generic_attr_num.value == 2
        assert retrieved_specific_two.generic_required_attr.value == "required"
        rels_two = await retrieved_specific_two.favorite_thing.get_relationships(db=db)
        assert len(rels_two) == 1
        assert rels_two[0].peer_id == initial_dataset["thing_two"].id
        assert isinstance(retrieved_specific_two.things, RelationshipManager)

        retrieved_specific_three = await NodeManager.get_one(
            db=db, branch=branch, id=initial_dataset["specific_three"].id
        )
        assert retrieved_specific_three.generic_attr_text.value == "Charlie"
        assert retrieved_specific_three.generic_attr_num.value == 3
        assert retrieved_specific_three.generic_required_attr.value is None
        rels_three = await retrieved_specific_three.favorite_thing.get_relationships(db=db)
        assert len(rels_three) == 1
        assert rels_three[0].peer_id == initial_dataset["thing_three"].id
        assert isinstance(retrieved_specific_three.things, RelationshipManager)

        # add and delete SPECIFIC_ONE_KIND instance with the client to validate schema update
        node = await client.create(
            kind=SPECIFIC_ONE_KIND,
            branch=branch.name,
            data={
                "generic_attr_text": "Edward",
                "generic_attr_num": 5,
                # no generic_required_attr set
                "favorite_thing": initial_dataset["thing_one"].id,
            },
        )
        await node.save()
        retrieved_node = await client.get(kind=SPECIFIC_ONE_KIND, branch=branch.name, id=node.id)
        assert retrieved_node.generic_attr_text.value == "Edward"
        assert retrieved_node.generic_attr_num.value == 5
        assert retrieved_node.generic_required_attr.value is None
        await node.delete()

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        generic_schema = updated_schema_branch.get(GENERIC_KIND, duplicate=False)
        assert set(generic_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
        }
        assert set(generic_schema.relationship_names) >= {"things", "favorite_thing"}
        generic_attr_text_schema = generic_schema.get_attribute("generic_attr_text")
        assert generic_attr_text_schema.default_value is None
        specific_one_schema = updated_schema_branch.get(SPECIFIC_ONE_KIND, duplicate=False)
        assert set(specific_one_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
        }
        assert set(specific_one_schema.local_attribute_names) == {"generic_attr_text", "generic_required_attr"}
        overridden_generic_attr_text_schema = specific_one_schema.get_attribute("generic_attr_text")
        assert overridden_generic_attr_text_schema.default_value == "this default"
        assert overridden_generic_attr_text_schema.order_weight == 1011
        overridden_generic_required_attr_schema = specific_one_schema.get_attribute("generic_required_attr")
        assert overridden_generic_required_attr_schema.optional is True
        assert set(specific_one_schema.relationship_names) >= {"things", "favorite_thing"}
        assert set(specific_one_schema.local_relationship_names) >= {"things"}
        overridden_things_rel_schema = specific_one_schema.get_relationship("things")
        assert overridden_things_rel_schema.max_count == 3
        assert overridden_things_rel_schema.order_weight == 3011
        specific_two_schema = updated_schema_branch.get(SPECIFIC_TWO_KIND, duplicate=False)
        assert set(specific_two_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
            "specific_attr_text",
        }
        assert set(specific_two_schema.local_attribute_names) == {"specific_attr_text"}
        assert set(specific_two_schema.relationship_names) >= {"things", "favorite_thing", "specific_things"}
        assert set(specific_two_schema.local_relationship_names) >= {"specific_things"}
        specific_three_schema = updated_schema_branch.get(SPECIFIC_THREE_KIND, duplicate=False)
        assert set(specific_three_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
            "specific_attr_num",
        }
        assert set(specific_three_schema.local_attribute_names) == {
            "generic_attr_text",
            "generic_required_attr",
            "specific_attr_num",
        }
        overridden_generic_attr_text_schema = specific_three_schema.get_attribute("generic_attr_text")
        assert overridden_generic_attr_text_schema.regex == "^[A-Z][a-z]+"
        assert overridden_generic_attr_text_schema.order_weight == 1033
        assert set(specific_three_schema.relationship_names) >= {"things", "favorite_thing"}
        assert "things" not in specific_three_schema.local_relationship_names
        assert "favorite_thing" not in specific_three_schema.local_relationship_names

        errors = await self.validate_database(
            db=db,
            branch=branch,
            inheriting_schemas=[
                updated_schema_branch.get_node(name=schema_kind, duplicate=False)
                for schema_kind in (SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND)
            ],
        )
        assert not errors

    async def _finalize_deleted_fields(self, db: InfrahubDatabase, branch: Branch, full_schema_dict: dict[str, Any]):
        current_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        for schema_dict in full_schema_dict.get("generics", []) + full_schema_dict.get("nodes", []):
            for attr in schema_dict.get("attributes", []):
                if attr.get("state") == HashableModelState.ABSENT.value:
                    schema = current_schema_branch.get(
                        name=schema_dict["namespace"] + schema_dict["name"], duplicate=False
                    )
                    attr_schema = schema.get_attribute(name=attr["name"])
                    attr["id"] = attr_schema.id
            for rel in schema_dict.get("relationships", []):
                if rel.get("state") == HashableModelState.ABSENT.value:
                    schema = current_schema_branch.get(
                        name=schema_dict["namespace"] + schema_dict["name"], duplicate=False
                    )
                    rel_schema = schema.get_relationship(name=rel["name"])
                    rel["id"] = rel_schema.id

    async def test_step03_check_delete_overridden_field(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_03: dict[str, Any],
    ):
        await self._finalize_deleted_fields(db=db, branch=branch, full_schema_dict=schema_step_03)
        success, response = await client.schema.check(schemas=[schema_step_03], branch=branch.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    SPECIFIC_THREE_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "generic_attr_text": {
                                        "added": {},
                                        "changed": {
                                            "id": None,
                                            "inherited": None,
                                            "regex": None,
                                            "order_weight": None,
                                            "parameters": {"added": {}, "changed": {"regex": None}, "removed": {}},
                                        },
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step03_load_schema_with_deleted_override(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_03: dict[str, Any],
    ):
        await self._finalize_deleted_fields(db=db, branch=branch, full_schema_dict=schema_step_03)
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_03], branch=branch.name)
        assert not response.errors

        await self._refresh_registry(db=db, branch=branch)
        retrieved_specific_one = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_one"].id)
        assert retrieved_specific_one.generic_attr_text.value == "Alpha"
        assert retrieved_specific_one.generic_attr_num.value == 1
        assert retrieved_specific_one.generic_required_attr.value == "required"
        rels_one = await retrieved_specific_one.favorite_thing.get_relationships(db=db)
        assert len(rels_one) == 1
        assert rels_one[0].peer_id == initial_dataset["thing_one"].id
        assert isinstance(retrieved_specific_one.things, RelationshipManager)

        retrieved_specific_two = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_two"].id)
        assert retrieved_specific_two.generic_attr_text.value == "Bravo"
        assert retrieved_specific_two.generic_attr_num.value == 2
        assert retrieved_specific_two.generic_required_attr.value == "required"
        rels_two = await retrieved_specific_two.favorite_thing.get_relationships(db=db)
        assert len(rels_two) == 1
        assert rels_two[0].peer_id == initial_dataset["thing_two"].id
        assert isinstance(retrieved_specific_two.things, RelationshipManager)

        retrieved_specific_three = await NodeManager.get_one(
            db=db, branch=branch, id=initial_dataset["specific_three"].id
        )
        assert retrieved_specific_three.generic_attr_text.value == "Charlie"
        assert retrieved_specific_three.generic_attr_num.value == 3
        assert retrieved_specific_three.generic_required_attr.value is None
        rels_three = await retrieved_specific_three.favorite_thing.get_relationships(db=db)
        assert len(rels_three) == 1
        assert rels_three[0].peer_id == initial_dataset["thing_three"].id
        assert isinstance(retrieved_specific_three.things, RelationshipManager)

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        generic_schema = updated_schema_branch.get(GENERIC_KIND, duplicate=False)
        assert set(generic_schema.attribute_names) == {
            "generic_attr_num",
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_required_attr",
        }
        assert set(generic_schema.relationship_names) >= {"things", "favorite_thing"}
        specific_one_schema = updated_schema_branch.get(SPECIFIC_ONE_KIND, duplicate=False)
        assert set(specific_one_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
        }
        assert set(specific_one_schema.local_attribute_names) == {"generic_attr_text", "generic_required_attr"}
        assert {"favorite_thing", "things"} <= set(specific_one_schema.relationship_names)
        specific_two_schema = updated_schema_branch.get(SPECIFIC_TWO_KIND, duplicate=False)
        assert set(specific_two_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
            "specific_attr_text",
        }
        assert set(specific_two_schema.local_attribute_names) == {"specific_attr_text"}
        assert set(specific_two_schema.relationship_names) >= {"favorite_thing", "specific_things", "things"}
        assert set(specific_two_schema.local_relationship_names) >= {"specific_things"}
        specific_three_schema = updated_schema_branch.get(SPECIFIC_THREE_KIND, duplicate=False)
        assert set(specific_three_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
            "specific_attr_num",
        }
        assert set(specific_three_schema.local_attribute_names) == {"specific_attr_num", "generic_required_attr"}
        generic_attr_text_schema = specific_three_schema.get_attribute("generic_attr_text")
        assert generic_attr_text_schema.regex is None
        assert generic_attr_text_schema.order_weight == 1111
        assert set(specific_three_schema.relationship_names) >= {"things", "favorite_thing"}
        assert "things" not in specific_three_schema.local_relationship_names
        assert "favorite_thing" not in specific_three_schema.local_relationship_names

        errors = await self.validate_database(
            db=db,
            branch=branch,
            inheriting_schemas=[
                updated_schema_branch.get_node(name=schema_kind, duplicate=False)
                for schema_kind in (SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND)
            ],
        )
        assert not errors

    async def test_step04_check_generic_weight_updates(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_04: dict[str, Any],
    ):
        success, response = await client.schema.check(schemas=[schema_step_04], branch=branch.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    GENERIC_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "generic_attr_text": {
                                        "added": {},
                                        "changed": {"order_weight": None},
                                        "removed": {},
                                    },
                                    "generic_attr_num": {
                                        "added": {},
                                        "changed": {"order_weight": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "things": {
                                        "added": {},
                                        "changed": {"order_weight": None},
                                        "removed": {},
                                    },
                                    "favorite_thing": {
                                        "added": {},
                                        "changed": {"order_weight": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step04_load_schema_with_updated_generic_weight(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_04: dict[str, Any],
    ):
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_04], branch=branch.name)
        assert not response.errors

        await self._refresh_registry(db=db, branch=branch)
        retrieved_specific_one = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_one"].id)
        assert retrieved_specific_one.generic_attr_text.value == "Alpha"
        assert retrieved_specific_one.generic_attr_num.value == 1
        assert retrieved_specific_one.generic_required_attr.value == "required"
        rels_one = await retrieved_specific_one.favorite_thing.get_relationships(db=db)
        assert len(rels_one) == 1
        assert rels_one[0].peer_id == initial_dataset["thing_one"].id
        assert isinstance(retrieved_specific_one.things, RelationshipManager)

        retrieved_specific_two = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_two"].id)
        assert retrieved_specific_two.generic_attr_text.value == "Bravo"
        assert retrieved_specific_two.generic_attr_num.value == 2
        assert retrieved_specific_two.generic_required_attr.value == "required"
        rels_two = await retrieved_specific_two.favorite_thing.get_relationships(db=db)
        assert len(rels_two) == 1
        assert rels_two[0].peer_id == initial_dataset["thing_two"].id
        assert isinstance(retrieved_specific_two.things, RelationshipManager)

        retrieved_specific_three = await NodeManager.get_one(
            db=db, branch=branch, id=initial_dataset["specific_three"].id
        )
        assert retrieved_specific_three.generic_attr_text.value == "Charlie"
        assert retrieved_specific_three.generic_attr_num.value == 3
        assert retrieved_specific_three.generic_required_attr.value is None
        rels_three = await retrieved_specific_three.favorite_thing.get_relationships(db=db)
        assert len(rels_three) == 1
        assert rels_three[0].peer_id == initial_dataset["thing_three"].id
        assert isinstance(retrieved_specific_three.things, RelationshipManager)

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        generic_schema = updated_schema_branch.get(GENERIC_KIND, duplicate=False)
        assert set(generic_schema.attribute_names) == {
            "generic_attr_num",
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_required_attr",
        }
        assert set(generic_schema.relationship_names) >= {"things", "favorite_thing"}
        weights_by_field_name = {
            field.name: field.order_weight for field in generic_schema.attributes + generic_schema.relationships
        }
        assert weights_by_field_name["generic_attr_text"] == 1112
        assert weights_by_field_name["generic_attr_num"] == 2223
        assert weights_by_field_name["things"] == 3334
        assert weights_by_field_name["favorite_thing"] == 4445
        specific_one_schema = updated_schema_branch.get(SPECIFIC_ONE_KIND, duplicate=False)
        assert set(specific_one_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
        }
        assert set(specific_one_schema.local_attribute_names) == {"generic_attr_text", "generic_required_attr"}
        assert {"favorite_thing", "things"} <= set(specific_one_schema.relationship_names)
        assert "things" in specific_one_schema.local_relationship_names
        assert "favorite_thing" not in specific_one_schema.local_relationship_names
        weights_by_field_name = {
            field.name: field.order_weight
            for field in specific_one_schema.attributes + specific_one_schema.relationships
        }
        assert weights_by_field_name["generic_attr_text"] == 1011
        assert weights_by_field_name["generic_attr_num"] == 2223
        assert weights_by_field_name["things"] == 3011
        assert weights_by_field_name["favorite_thing"] == 4445
        specific_two_schema = updated_schema_branch.get(SPECIFIC_TWO_KIND, duplicate=False)
        assert set(specific_two_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
            "specific_attr_text",
        }
        assert set(specific_two_schema.local_attribute_names) == {"specific_attr_text"}
        assert set(specific_two_schema.relationship_names) >= {"favorite_thing", "specific_things", "things"}
        assert set(specific_two_schema.local_relationship_names) >= {"specific_things"}
        weights_by_field_name = {
            field.name: field.order_weight
            for field in specific_two_schema.attributes + specific_two_schema.relationships
        }
        assert weights_by_field_name["generic_attr_text"] == 1112
        assert weights_by_field_name["generic_attr_num"] == 2223
        assert weights_by_field_name["things"] == 3334
        assert weights_by_field_name["favorite_thing"] == 4445
        specific_three_schema = updated_schema_branch.get(SPECIFIC_THREE_KIND, duplicate=False)
        assert set(specific_three_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
            "specific_attr_num",
        }
        assert set(specific_three_schema.local_attribute_names) == {"specific_attr_num", "generic_required_attr"}
        generic_attr_text_schema = specific_three_schema.get_attribute("generic_attr_text")
        assert generic_attr_text_schema.regex is None
        assert set(specific_three_schema.relationship_names) >= {"things", "favorite_thing"}
        assert "things" not in specific_three_schema.local_relationship_names
        assert "favorite_thing" not in specific_three_schema.local_relationship_names
        weights_by_field_name = {
            field.name: field.order_weight for field in generic_schema.attributes + generic_schema.relationships
        }
        assert weights_by_field_name["generic_attr_text"] == 1112
        assert weights_by_field_name["generic_attr_num"] == 2223
        assert weights_by_field_name["things"] == 3334
        assert weights_by_field_name["favorite_thing"] == 4445

        errors = await self.validate_database(
            db=db,
            branch=branch,
            inheriting_schemas=[
                updated_schema_branch.get_node(name=schema_kind, duplicate=False)
                for schema_kind in (SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND)
            ],
        )
        assert not errors

    async def test_step05_check_delete_generic_fields(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_05: dict[str, Any],
    ):
        await self._finalize_deleted_fields(db=db, branch=branch, full_schema_dict=schema_step_05)
        success, response = await client.schema.check(schemas=[schema_step_05], branch=branch.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    GENERIC_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {},
                                "removed": {
                                    "generic_attr_text": None,
                                    "generic_required_attr": None,
                                },
                            },
                            "relationships": {
                                "added": {},
                                "changed": {},
                                "removed": {"things": None},
                            },
                        },
                        "removed": {},
                    },
                    SPECIFIC_TWO_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "generic_attr_text": {
                                        "added": {},
                                        "changed": {"state": None},
                                        "removed": {},
                                    },
                                    "generic_required_attr": {
                                        "added": {},
                                        "changed": {"state": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "things": {
                                        "added": {},
                                        "changed": {"state": None},
                                        "removed": {},
                                    }
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    SPECIFIC_THREE_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "generic_attr_text": {
                                        "added": {},
                                        "changed": {"state": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "things": {
                                        "added": {},
                                        "changed": {"state": None},
                                        "removed": {},
                                    }
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step05_load_schema_with_generic_deletes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_05: dict[str, Any],
    ):
        await self._finalize_deleted_fields(db=db, branch=branch, full_schema_dict=schema_step_05)
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_05], branch=branch.name)
        assert not response.errors

        await self._refresh_registry(db=db, branch=branch)
        retrieved_specific_one = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_one"].id)
        assert retrieved_specific_one.generic_attr_text.value == "Alpha"
        assert retrieved_specific_one.generic_attr_num.value == 1
        assert retrieved_specific_one.generic_required_attr.value == "required"
        rels_one = await retrieved_specific_one.favorite_thing.get_relationships(db=db)
        assert len(rels_one) == 1
        assert rels_one[0].peer_id == initial_dataset["thing_one"].id
        assert isinstance(retrieved_specific_one.things, RelationshipManager)

        retrieved_specific_two = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_two"].id)
        assert not hasattr(retrieved_specific_two, "generic_attr_text")
        assert retrieved_specific_two.generic_attr_num.value == 2
        assert not hasattr(retrieved_specific_two, "generic_required_attr")
        rels_two = await retrieved_specific_two.favorite_thing.get_relationships(db=db)
        assert len(rels_two) == 1
        assert rels_two[0].peer_id == initial_dataset["thing_two"].id
        assert not hasattr(retrieved_specific_two, "things")

        retrieved_specific_three = await NodeManager.get_one(
            db=db, branch=branch, id=initial_dataset["specific_three"].id
        )
        assert not hasattr(retrieved_specific_three, "generic_attr_text")
        assert retrieved_specific_three.generic_attr_num.value == 3
        assert retrieved_specific_three.generic_required_attr.value is None
        rels_two = await retrieved_specific_three.favorite_thing.get_relationships(db=db)
        assert len(rels_two) == 1
        assert rels_two[0].peer_id == initial_dataset["thing_three"].id
        assert not hasattr(retrieved_specific_three, "things")

        # verify add and delete using client
        await client.schema.get(kind=SPECIFIC_ONE_KIND, branch=branch.name, refresh=True)
        await client.schema.get(kind=SPECIFIC_THREE_KIND, branch=branch.name, refresh=True)
        node = await client.create(
            kind=SPECIFIC_ONE_KIND,
            branch=branch.name,
            data={
                "generic_attr_text": "Frank",
            },
        )
        await node.save()
        retrieved_node = await client.get(kind=SPECIFIC_ONE_KIND, branch=branch.name, id=node.id)
        assert retrieved_node.generic_attr_text.value == "Frank"
        assert retrieved_node.generic_required_attr.value is None
        await node.delete()
        node = await client.create(
            kind=SPECIFIC_THREE_KIND,
            branch=branch.name,
            data={
                "generic_attr_num": 6,
                "specific_attr_num": 66,
            },
        )
        await node.save()
        retrieved_node = await client.get(kind=SPECIFIC_THREE_KIND, branch=branch.name, id=node.id)
        assert retrieved_node.generic_attr_num.value == 6
        assert retrieved_node.specific_attr_num.value == 66
        assert retrieved_node.generic_required_attr.value is None
        await node.delete()

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        generic_schema = updated_schema_branch.get(GENERIC_KIND, duplicate=False)
        assert set(generic_schema.attribute_names) == {"generic_attr_num", "generic_attr_text_new"}
        assert "things" not in generic_schema.relationship_names
        assert "favorite_thing" in generic_schema.relationship_names
        specific_one_schema = updated_schema_branch.get(SPECIFIC_ONE_KIND, duplicate=False)
        assert set(specific_one_schema.attribute_names) == {
            "generic_attr_text",
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
        }
        assert set(specific_one_schema.local_attribute_names) == {"generic_attr_text", "generic_required_attr"}
        overridden_generic_attr_text_schema = specific_one_schema.get_attribute("generic_attr_text")
        assert overridden_generic_attr_text_schema.default_value == "this default"
        assert overridden_generic_attr_text_schema.order_weight == 1011
        assert set(specific_one_schema.relationship_names) >= {"things", "favorite_thing"}
        assert set(specific_one_schema.local_relationship_names) >= {"things"}
        overridden_things_rel_schema = specific_one_schema.get_relationship("things")
        assert overridden_things_rel_schema.max_count == 3
        assert overridden_things_rel_schema.order_weight == 3011
        specific_two_schema = updated_schema_branch.get(SPECIFIC_TWO_KIND, duplicate=False)
        assert set(specific_two_schema.attribute_names) == {
            "generic_attr_text_new",
            "generic_attr_num",
            "specific_attr_text",
        }
        assert set(specific_two_schema.local_attribute_names) == {"specific_attr_text"}
        assert set(specific_two_schema.relationship_names) >= {"favorite_thing", "specific_things"}
        assert "things" not in specific_two_schema.relationship_names
        assert set(specific_two_schema.local_relationship_names) >= {"specific_things"}
        specific_three_schema = updated_schema_branch.get(SPECIFIC_THREE_KIND, duplicate=False)
        assert set(specific_three_schema.attribute_names) == {
            "generic_attr_num",
            "generic_attr_text_new",
            "specific_attr_num",
            "generic_required_attr",
        }
        assert set(specific_three_schema.local_attribute_names) == {"specific_attr_num", "generic_required_attr"}
        assert set(specific_three_schema.relationship_names) >= {"favorite_thing"}
        assert "favorite_thing" not in specific_three_schema.local_relationship_names

        errors = await self.validate_database(
            db=db,
            branch=branch,
            inheriting_schemas=[
                updated_schema_branch.get_node(name=schema_kind, duplicate=False)
                for schema_kind in (SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND)
            ],
        )
        assert not errors

    async def test_step06_check_deleted_overridden_fields(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_06: dict[str, Any],
    ):
        await self._finalize_deleted_fields(db=db, branch=branch, full_schema_dict=schema_step_06)
        success, response = await client.schema.check(schemas=[schema_step_06], branch=branch.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    SPECIFIC_ONE_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {},
                                "removed": {"generic_attr_text": None},
                            },
                            "relationships": {
                                "added": {},
                                "changed": {},
                                "removed": {"things": None},
                            },
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step06_load_schema_with_override_deletes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset,
        branch: Branch,
        schema_step_06: dict[str, Any],
    ):
        await self._finalize_deleted_fields(db=db, branch=branch, full_schema_dict=schema_step_06)
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_06], branch=branch.name)
        assert not response.errors

        await self._refresh_registry(db=db, branch=branch)
        retrieved_specific_one = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_one"].id)
        assert not hasattr(retrieved_specific_one, "generic_attr_text")
        assert retrieved_specific_one.generic_attr_num.value == 1
        assert retrieved_specific_one.generic_required_attr.value == "required"
        rels_one = await retrieved_specific_one.favorite_thing.get_relationships(db=db)
        assert len(rels_one) == 1
        assert rels_one[0].peer_id == initial_dataset["thing_one"].id
        assert not hasattr(retrieved_specific_one, "things")

        retrieved_specific_two = await NodeManager.get_one(db=db, branch=branch, id=initial_dataset["specific_two"].id)
        assert not hasattr(retrieved_specific_two, "generic_attr_text")
        assert retrieved_specific_two.generic_attr_num.value == 2
        assert not hasattr(retrieved_specific_two, "generic_required_attr")
        rels_two = await retrieved_specific_two.favorite_thing.get_relationships(db=db)
        assert len(rels_two) == 1
        assert rels_two[0].peer_id == initial_dataset["thing_two"].id
        assert not hasattr(retrieved_specific_two, "things")

        retrieved_specific_threee = await NodeManager.get_one(
            db=db, branch=branch, id=initial_dataset["specific_three"].id
        )
        assert not hasattr(retrieved_specific_threee, "generic_attr_text")
        assert retrieved_specific_threee.generic_attr_num.value == 3
        assert retrieved_specific_threee.generic_required_attr.value is None
        rels_three = await retrieved_specific_threee.favorite_thing.get_relationships(db=db)
        assert len(rels_three) == 1
        assert rels_three[0].peer_id == initial_dataset["thing_three"].id
        assert not hasattr(retrieved_specific_threee, "things")

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        generic_schema = updated_schema_branch.get(GENERIC_KIND, duplicate=False)
        assert set(generic_schema.attribute_names) == {"generic_attr_num", "generic_attr_text_new"}
        assert "things" not in generic_schema.relationship_names
        assert "favorite_thing" in generic_schema.relationship_names
        specific_one_schema = updated_schema_branch.get(SPECIFIC_ONE_KIND, duplicate=False)
        assert set(specific_one_schema.attribute_names) == {
            "generic_attr_text_new",
            "generic_attr_num",
            "generic_required_attr",
        }
        assert set(specific_one_schema.local_attribute_names) == {"generic_required_attr"}
        assert "things" not in specific_one_schema.relationship_names
        assert "favorite_thing" in specific_one_schema.relationship_names
        specific_two_schema = updated_schema_branch.get(SPECIFIC_TWO_KIND, duplicate=False)
        assert set(specific_two_schema.attribute_names) == {
            "generic_attr_text_new",
            "generic_attr_num",
            "specific_attr_text",
        }
        assert set(specific_two_schema.local_attribute_names) == {"specific_attr_text"}
        assert set(specific_two_schema.relationship_names) >= {"favorite_thing", "specific_things"}
        assert "things" not in specific_two_schema.relationship_names
        assert set(specific_two_schema.local_relationship_names) >= {"specific_things"}
        specific_three_schema = updated_schema_branch.get(SPECIFIC_THREE_KIND, duplicate=False)
        assert set(specific_three_schema.attribute_names) == {
            "generic_attr_text_new",
            "generic_attr_num",
            "specific_attr_num",
            "generic_required_attr",
        }
        assert set(specific_three_schema.local_attribute_names) == {"specific_attr_num", "generic_required_attr"}
        assert set(specific_three_schema.relationship_names) >= {"favorite_thing"}
        assert "things" not in specific_three_schema.relationship_names
        assert "favorite_thing" not in specific_three_schema.local_relationship_names

        errors = await self.validate_database(
            db=db,
            branch=branch,
            inheriting_schemas=[
                updated_schema_branch.get_node(name=schema_kind, duplicate=False)
                for schema_kind in (SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND)
            ],
        )
        assert not errors

    async def test_final_validate(self, db: InfrahubDatabase):
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)


class TestSchemaLifecycleGenericUpdates(SchemaLifecycleGenericBase):
    async def validate_database(
        self, db: InfrahubDatabase, branch: Branch, inheriting_schemas: list[NodeSchema]
    ) -> list[str]:
        errors = await self._validate_inherited_schema_fields(
            db=db, branch=branch, inheriting_schemas=inheriting_schemas
        )
        errors.extend(await validate_no_duplicate_attributes(db=db, branch=branch))
        return errors

    async def _validate_inherited_schema_fields(
        self, db: InfrahubDatabase, branch: Branch, inheriting_schemas: list[NodeSchema]
    ) -> list[str]:
        """
        Validate the following:
         - SchemaNode nodes do not have relationship to SchemaAttribute or SchemaRelationship nodes for
            any inherited relationships or attributes
         - SchemaNode nodes have relationship to SchemaAttribute or SchemaRelationship nodes for
            all local relationships and attributes
        """
        node_kind_map: dict[str, list[str]] = {}
        for node_schema in inheriting_schemas:
            if node_schema.namespace not in node_kind_map:
                node_kind_map[node_schema.namespace] = []
            node_kind_map[node_schema.namespace].append(node_schema.name)
        params = {
            "node_kind_map": node_kind_map,
        }
        branch_filter, branch_params = branch.get_query_filter_path()
        params.update(branch_params)
        query = """
MATCH (schema_node:SchemaNode)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(ns_value:AttributeValue)
WHERE $node_kind_map[ns_value.value] IS NOT NULL
MATCH (schema_node)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(name_value:AttributeValue)
WHERE name_value.value IN $node_kind_map[ns_value.value]
WITH schema_node, ns_value.value + name_value.value AS node_kind
MATCH (schema_node)-[:IS_RELATED]-(:Relationship {name: "schema__node__relationships"})-[:IS_RELATED]-(:SchemaRelationship)
    -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(rnv:AttributeValue)
WITH DISTINCT schema_node, node_kind, rnv
CALL (schema_node, rnv) {
    MATCH path = (schema_node)-[r1:IS_RELATED]-(:Relationship {name: "schema__node__relationships"})-[r2:IS_RELATED]-(:SchemaRelationship)
        -[r3:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r4:HAS_VALUE]->(rnv)
    WHERE all(r IN relationships(path) WHERE %(branch_filter)s)
    RETURN all(r IN relationships(path) WHERE r.status = "active") AS is_active
    ORDER BY (r1.branch_level + r2.branch_level + r3.branch_level + r4.branch_level) DESC,
        r4.from DESC, r3.from DESC, r2.from DESC, r1.from DESC
    LIMIT 1
}
WITH schema_node, node_kind, rnv, is_active
WHERE is_active = TRUE
WITH schema_node, node_kind, collect(rnv.value) AS relationship_names
MATCH (schema_node)-[:IS_RELATED]-(:Relationship {name: "schema__node__attributes"})-[:IS_RELATED]-(:SchemaAttribute)
    -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(anv:AttributeValue)
WITH DISTINCT schema_node, node_kind, relationship_names, anv
CALL (schema_node, anv) {
    MATCH path = (schema_node)-[r1:IS_RELATED]-(:Relationship {name: "schema__node__attributes"})-[r2:IS_RELATED]-(:SchemaAttribute)
        -[r3:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[r4:HAS_VALUE]->(anv)
    WHERE all(r IN relationships(path) WHERE %(branch_filter)s)
    RETURN all(r IN relationships(path) WHERE r.status = "active") AS is_active
    ORDER BY (r1.branch_level + r2.branch_level + r3.branch_level + r4.branch_level) DESC,
        r4.from DESC, r3.from DESC, r2.from DESC, r1.from DESC
    LIMIT 1
}
WITH node_kind, relationship_names, anv, is_active
WHERE is_active = TRUE
RETURN node_kind, relationship_names, collect(anv.value) AS attribute_names
        """ % {"branch_filter": branch_filter}
        results = await db.execute_query(query=query, params=params)
        errors = []

        schema_by_kind = {schema.kind: schema for schema in inheriting_schemas}
        for result in results:
            node_kind = result.get("node_kind")
            db_relationship_names = set(result.get("relationship_names"))
            db_attribute_names = set(result.get("attribute_names"))
            node_schema = schema_by_kind[node_kind]
            expected_local_rels = set(node_schema.local_relationship_names)
            expected_local_attrs = set(node_schema.local_attribute_names)
            for extra_generic_rel in db_relationship_names - expected_local_rels:
                errors.append(
                    f"Node schema '{node_kind}' has a relationship to generic-only relationship '{extra_generic_rel}'"
                )
            for extra_generic_attr in db_attribute_names - expected_local_attrs:
                errors.append(
                    f"Node schema '{node_kind}' has a relationship to generic-only attribute '{extra_generic_attr}'"
                )
            for missing_local_rel in expected_local_rels - db_relationship_names:
                errors.append(
                    f"Node schema '{node_kind}' is missing a relationship to local relationship '{missing_local_rel}'"
                )
            for missing_local_attr in expected_local_attrs - db_attribute_names:
                errors.append(
                    f"Node schema '{node_kind}' is missing a relationship to local attribute '{missing_local_attr}'"
                )
        return errors


class TestSchemaLifecycleGenericUpdatedWithLegacyDuplicates(SchemaLifecycleGenericBase):
    """
    Same tests as TestSchemaLifecycleGenericUpdates, but start with duplicated inherited SchemaAttributes
    and SchemaRelationships in the database b/c this is how we used to store inherited fields of a schema
    And skip the database-level verification in TestSchemaLifecycleGenericUpdates b/c it would fail
    """

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_objects: dict[str, Node],
        client: InfrahubClient,
        branch_name: str,
    ) -> dict[str, Node]:
        # add duplicative inherited attrs and rels to database for inheriting schemas
        # b/c this is how data used to be stored
        main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        attribute_schema = main_schema_branch.get_node(name="SchemaAttribute", duplicate=False)
        relationship_schema = main_schema_branch.get_node(name="SchemaRelationship", duplicate=False)
        for schema_kind in [SPECIFIC_ONE_KIND, SPECIFIC_TWO_KIND, SPECIFIC_THREE_KIND]:
            node_schema = main_schema_branch.get(schema_kind)
            node_schema_instance = await NodeManager.get_one(db=db, branch=default_branch, id=node_schema.get_id())
            for attr_name in ("generic_attr_text", "generic_attr_num"):
                attr = node_schema.get_attribute(attr_name)
                new_attr = await registry.schema.create_attribute_in_db(
                    db=db, branch=default_branch, schema=attribute_schema, parent=node_schema_instance, item=attr
                )
                attr.id = new_attr.id
            for rel_name in ("things", "favorite_thing"):
                rel = node_schema.get_relationship(rel_name)
                new_rel = await registry.schema.create_relationship_in_db(
                    db=db, branch=default_branch, schema=relationship_schema, parent=node_schema_instance, item=rel
                )
                rel.id = new_rel.id
            main_schema_branch.set(name=schema_kind, schema=node_schema)
        await client.branch.create(branch_name=branch_name, wait_until_completion=True)
        return initial_objects

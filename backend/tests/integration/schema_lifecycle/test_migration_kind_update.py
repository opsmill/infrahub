from typing import Any

import pytest
from infrahub_sdk.client import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from infrahub.exceptions import SchemaNotFoundError
from tests.helpers.db_validation import verify_no_duplicate_paths

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

GENERIC_KIND = "TestingGeneric"
SPECIFIC_ONE_KIND = "TestingSpecificOne"
SPECIFIC_ONE_KIND_UPDATED = "TestingSpecificOneNew"
THING_KIND = "TestingThing"
BRANCH_ONE = "branch-one"


class TestKindUpdateMigration(TestSchemaLifecycleBase):
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
    def schema_step_01(
        self,
        schema_generic_base,
        schema_specific_one_base,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_base],
            "nodes": [schema_specific_one_base, schema_thing],
        }

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
        await specific_one.new(db=db, generic_attr_text="Alpha", generic_attr_num=1, favorite_thing=thing_one)
        await specific_one.save(db=db)

        deleted_specific_one = await Node.init(schema=SPECIFIC_ONE_KIND, db=db)
        await deleted_specific_one.new(
            db=db, generic_attr_text="Deleted-Alpha", generic_attr_num=-1, favorite_thing=thing_one
        )
        await deleted_specific_one.save(db=db)
        await deleted_specific_one.delete(db=db)

        objs = {
            "thing_one": thing_one,
            "thing_two": thing_two,
            "thing_three": thing_three,
            "specific_one": specific_one,
        }
        return objs

    @pytest.fixture(scope="class")
    def schema_specific_one_new_kind(self) -> dict[str, Any]:
        return {
            "name": "SpecificOneNew",
            "namespace": "Testing",
            "inherit_from": ["TestingGeneric"],
        }

    @pytest.fixture(scope="class")
    def schema_step_02(
        self,
        schema_generic_base,
        schema_specific_one_new_kind,
        schema_thing,
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_base],
            "nodes": [schema_specific_one_new_kind, schema_thing],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_objects: dict[str, Node],
    ) -> dict[str, Node]:
        return initial_objects

    @pytest.fixture(scope="class")
    async def branch_one(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name=BRANCH_ONE)

    @pytest.fixture(scope="class")
    async def specific_one_update_01(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        branch_one: Branch,
    ) -> Node:
        thing_two_id = initial_objects["thing_two"].id
        branch_specific_one = await NodeManager.get_one(db=db, branch=branch_one, id=initial_objects["specific_one"].id)
        branch_specific_one.generic_attr_text.value += "01"
        await branch_specific_one.things.update(db=db, data=[thing_two_id])
        await branch_specific_one.save(db=db)
        return branch_specific_one

    @pytest.fixture(scope="class")
    async def specific_one_update_02(
        self,
        db: InfrahubDatabase,
        initial_objects: dict[str, Node],
        specific_one_update_01: Node,
        branch_one: Branch,
    ) -> Node:
        thing_three_id = initial_objects["thing_three"].id
        branch_specific_one = await NodeManager.get_one(db=db, branch=branch_one, id=initial_objects["specific_one"].id)
        branch_specific_one.generic_attr_text.value += "02"
        await branch_specific_one.things.update(db=db, data=[thing_three_id])
        await branch_specific_one.save(db=db)
        return branch_specific_one

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset):
        all_specifics = await registry.manager.query(db=db, schema=GENERIC_KIND)
        assert len(all_specifics) == 1

        specific_ones = await registry.manager.query(db=db, schema=SPECIFIC_ONE_KIND)
        assert len(specific_ones) == 1

    async def test_step02_check_change_node_kind(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initial_dataset,
        branch_one: Branch,
        schema_step_02: dict[str, Any],
    ):
        current_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        current_specific_one_schema = current_schema_branch.get_node(name=SPECIFIC_ONE_KIND, duplicate=False)
        for schema_dict in schema_step_02["nodes"]:
            if SPECIFIC_ONE_KIND_UPDATED.endswith(schema_dict["name"]):
                schema_dict["id"] = current_specific_one_schema.get_id()

        success, response = await client.schema.check(schemas=[schema_step_02], branch=BRANCH_ONE)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {SPECIFIC_ONE_KIND_UPDATED: {"added": {}, "changed": {"name": None}, "removed": {}}},
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step02_load_node_kind_change(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initial_dataset,
        branch_one: Branch,
        schema_step_02: dict[str, Any],
        specific_one_update_01: Node,
    ):
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_02], branch=BRANCH_ONE)
        assert not response.errors

        retrieved_specific_one = await NodeManager.get_one(
            db=db, branch=branch_one, id=initial_dataset["specific_one"].id
        )
        assert retrieved_specific_one.get_kind() == SPECIFIC_ONE_KIND_UPDATED
        assert retrieved_specific_one.generic_attr_text.value == specific_one_update_01.generic_attr_text.value  # type: ignore[attr-defined]
        retrieved_things_rels = await retrieved_specific_one.things.get_relationships(db=db)
        updated_things_rels = await specific_one_update_01.things.get_relationships(db=db)  # type: ignore[attr-defined]
        assert len(retrieved_things_rels) == 1
        assert len(updated_things_rels) == 1
        assert retrieved_things_rels[0].get_peer_id() == updated_things_rels[0].get_peer_id()

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_one)
        with pytest.raises(SchemaNotFoundError):
            updated_schema_branch.get(SPECIFIC_ONE_KIND)
        updated_specific_one_schema = updated_schema_branch.get(name=SPECIFIC_ONE_KIND_UPDATED, duplicate=False)
        main_specific_one_schema = registry.schema.get(name=SPECIFIC_ONE_KIND, branch=branch_one, duplicate=False)
        assert updated_specific_one_schema.get_id() == main_specific_one_schema.get_id()

    async def test_step02_update_migrated_node(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initial_dataset,
        branch_one: Branch,
        schema_step_02: dict[str, Any],
        specific_one_update_02: Node,
    ):
        retrieved_specific_one = await NodeManager.get_one(
            db=db, branch=branch_one, id=initial_dataset["specific_one"].id
        )
        assert retrieved_specific_one.get_kind() == SPECIFIC_ONE_KIND_UPDATED
        assert retrieved_specific_one.generic_attr_text.value == specific_one_update_02.generic_attr_text.value  # type: ignore[attr-defined]
        retrieved_things_rels = await retrieved_specific_one.things.get_relationships(db=db)
        updated_things_rels = await specific_one_update_02.things.get_relationships(db=db)  # type: ignore[attr-defined]
        assert len(retrieved_things_rels) == 1
        assert len(updated_things_rels) == 1
        assert retrieved_things_rels[0].get_peer_id() == updated_things_rels[0].get_peer_id()

    async def validate_duplicate_nodes(self, db: InfrahubDatabase, kind_update_map: dict[str, str]) -> list[str]:
        query = """
        MATCH (n:Node)
        WHERE $kind_update_map[n.kind] IS NOT NULL
        MATCH (updated_n:Node {uuid: n.uuid})
        WHERE updated_n.kind = $kind_update_map[n.kind]
        RETURN n, collect(updated_n) AS migrated_n_list
        """
        results = await db.execute_query(query=query, params={"kind_update_map": kind_update_map})
        errors = []
        for result in results:
            migrated_n_list = result.get("migrated_n_list")
            if len(migrated_n_list) == 1:
                continue
            original_n = result.get("n")
            original_kind = original_n.get("kind")
            node_uuid = original_n.get("uuid")
            errors.append(
                f"{original_kind} '{node_uuid}' has {len(migrated_n_list)} migrated nodes. Expected exactly 1"
            )
        return errors

    async def test_step03_merge_node_kind_change_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initial_dataset,
        branch_one: Branch,
        schema_step_02: dict[str, Any],
        schema_specific_one_base: dict[str, Any],
        schema_specific_one_new_kind: dict[str, Any],
        specific_one_update_02: Node,
    ):
        is_success = await client.branch.merge(branch_name=BRANCH_ONE)
        assert is_success

        old_kind = schema_specific_one_base["namespace"] + schema_specific_one_base["name"]
        new_kind = schema_specific_one_new_kind["namespace"] + schema_specific_one_new_kind["name"]
        errors = await self.validate_duplicate_nodes(db=db, kind_update_map={old_kind: new_kind})
        assert errors == []
        await verify_no_duplicate_paths(db=db)

        retrieved_specific_one = await NodeManager.get_one(
            db=db, branch=default_branch, id=initial_dataset["specific_one"].id
        )
        assert retrieved_specific_one.get_kind() == SPECIFIC_ONE_KIND_UPDATED
        assert retrieved_specific_one.generic_attr_text.value == specific_one_update_02.generic_attr_text.value  # type: ignore[attr-defined]
        retrieved_things_rels = await retrieved_specific_one.things.get_relationships(db=db)
        updated_things_rels = await specific_one_update_02.things.get_relationships(db=db)  # type: ignore[attr-defined]
        assert len(retrieved_things_rels) == 1
        assert len(updated_things_rels) == 1
        assert retrieved_things_rels[0].get_peer_id() == updated_things_rels[0].get_peer_id()

    async def test_final_validate(self, db: InfrahubDatabase):
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)

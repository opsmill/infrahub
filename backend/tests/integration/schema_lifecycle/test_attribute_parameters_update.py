from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreNumberPool
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import (
    NumberAttributeParameters,
    NumberPoolParameters,
    TextAttributeParameters,
)
from infrahub.pools.number_pool_repository import NumberPoolRepository
from tests.helpers.number_pool import run_schema_updated_workflow
from tests.helpers.schema import load_schema as load_schema_root
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.branch.models import Branch
    from infrahub.core.schema.node_schema import NodeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


LEGACY_KIND = "TestingThingLegacy"
NEW_KIND = "TestingThing"


class TestUpdateAttributeParameters(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def schema_thing_legacy(self) -> dict[str, Any]:
        return {
            "name": "ThingLegacy",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Thing",
            "attributes": [
                {"name": "value", "kind": "Text", "regex": "old", "min_length": 0, "max_length": 4},
                {
                    "name": "assigned_number",
                    "kind": "NumberPool",
                    "optional": False,
                    "read_only": True,
                    "parameters": {"start_range": 10, "end_range": 200},
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_thing(self) -> dict[str, Any]:
        return {
            "name": "Thing",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Thing",
            "attributes": [
                {"name": "value", "kind": "Text", "parameters": {"regex": "newnew", "min_length": 5, "max_length": 6}},
                {"name": "number", "kind": "Number", "parameters": {"min_value": 0, "max_value": 10}},
                {
                    "name": "assigned_number",
                    "kind": "NumberPool",
                    "optional": False,
                    "read_only": True,
                    "parameters": {"start_range": 5, "end_range": 10000},
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step_01(
        self,
        schema_thing_legacy: dict[str, Any],
        schema_thing: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_legacy, schema_thing],
        }

    @pytest.fixture(scope="class")
    def regex_02(self) -> str:
        return "regex02"

    @pytest.fixture(scope="class")
    def min_length_02(self) -> int:
        return 8

    @pytest.fixture(scope="class")
    def max_length_02(self) -> int:
        return 15

    @pytest.fixture(scope="class")
    def schema_thing_legacy_02(self, regex_02: str, min_length_02: int, max_length_02: int) -> dict[str, Any]:
        return {
            "name": "ThingLegacy",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Thing",
            "attributes": [
                {
                    "name": "value",
                    "kind": "Text",
                    "regex": regex_02,
                    "min_length": min_length_02,
                    "max_length": max_length_02,
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_thing_02(self, regex_02: str, min_length_02: int, max_length_02: int) -> dict[str, Any]:
        return {
            "name": "Thing",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Thing",
            "attributes": [
                {
                    "name": "value",
                    "kind": "Text",
                    "parameters": {"regex": regex_02, "min_length": min_length_02, "max_length": max_length_02},
                },
                {
                    "name": "number",
                    "kind": "Number",
                    "parameters": {"min_value": 20, "max_value": 30},
                },
                {
                    "name": "assigned_number",
                    "kind": "NumberPool",
                    "optional": False,
                    "read_only": True,
                    "parameters": {"start_range": 50, "end_range": 1200},
                },
            ],
        }

    @pytest.fixture(scope="class")
    def schema_step_02(
        self,
        schema_thing_legacy_02: dict[str, Any],
        schema_thing_02: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_thing_legacy_02, schema_thing_02],
        }

    @pytest.fixture(scope="class")
    def schema_thing_03_excluding_held_value(self, schema_thing_02: dict[str, Any]) -> dict[str, Any]:
        return self._thing_with_pool_parameters(schema_thing_02, parameters={"start_range": 100, "end_range": 200})

    @pytest.fixture(scope="class")
    def schema_thing_04_ranges_excluding_held_value(self, schema_thing_02: dict[str, Any]) -> dict[str, Any]:
        return self._thing_with_pool_parameters(
            schema_thing_02, parameters={"ranges": [{"start": 10, "end": 20}, {"start": 100, "end": 200}]}
        )

    @staticmethod
    def _thing_with_pool_parameters(schema_thing: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
        thing = deepcopy(schema_thing)
        for attribute in thing["attributes"]:
            if attribute["name"] == "assigned_number":
                attribute["parameters"] = parameters
        return thing

    @pytest.fixture(scope="class")
    async def load_schema_01(
        self, db: InfrahubDatabase, default_branch: Branch, schema_step_01: dict[str, Any]
    ) -> None:
        schema_root = SchemaRoot(**schema_step_01)
        await load_schema_root(db=db, branch_name=default_branch.name, schema=schema_root, update_db=True)

        # delete parameters from the LegacyThing schema attribute b/c legacy AttributeSchemas will not have them
        query = """
        MATCH (legacy_schema:SchemaNode)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(av {value: "ThingLegacy"})
        MATCH (legacy_schema)-[:IS_RELATED]-(:Relationship {name: "schema__node__attributes"})-[:IS_RELATED]-(schema_attr:SchemaAttribute)
        MATCH (schema_attr)-[:HAS_ATTRIBUTE]->(params_attr:Attribute {name: "parameters"})
        DETACH DELETE params_attr
        """
        await db.execute_query(query=query)

    def _validate_schema_value_parameters(
        self, schema: NodeSchema, regex: str | None, min_length: int | None, max_length: int | None
    ):
        value_attr = schema.get_attribute("value")
        assert value_attr.regex == regex
        assert value_attr.min_length == min_length
        assert value_attr.max_length == max_length
        assert isinstance(value_attr.parameters, TextAttributeParameters)
        assert value_attr.parameters.regex == regex
        assert value_attr.parameters.min_length == min_length
        assert value_attr.parameters.max_length == max_length

    def _validate_schema_number_parameters(self, schema: NodeSchema, min_value: int | None, max_value: int | None):
        number_attr = schema.get_attribute("number")
        assert isinstance(number_attr.parameters, NumberAttributeParameters)
        assert number_attr.parameters.min_value == min_value
        assert number_attr.parameters.max_value == max_value

    def _validate_schema_numberpool_parameters(self, schema: NodeSchema, start_range: int, end_range: int) -> None:
        number_attr = schema.get_attribute("assigned_number")
        assert isinstance(number_attr.parameters, NumberPoolParameters)
        assert number_attr.parameters.start_range == start_range
        assert number_attr.parameters.end_range == end_range
        assert number_attr.parameters.ranges == []

    async def test_schema_01_is_correct(
        self, db: InfrahubDatabase, default_branch: Branch, load_schema_01: None
    ) -> None:
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch.name)

        legacy_schema = schema_branch.get_node(name=LEGACY_KIND, duplicate=False)
        self._validate_schema_value_parameters(schema=legacy_schema, regex="old", min_length=0, max_length=4)

        new_schema = schema_branch.get_node(name=NEW_KIND, duplicate=False)
        self._validate_schema_value_parameters(schema=new_schema, regex="newnew", min_length=5, max_length=6)
        self._validate_schema_number_parameters(schema=new_schema, min_value=0, max_value=10)
        self._validate_schema_numberpool_parameters(schema=new_schema, start_range=5, end_range=10000)

    async def test_schema02_load_update(
        self,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_02: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step_02], branch=default_branch.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    LEGACY_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "value": {
                                        "added": {},
                                        "changed": {
                                            "regex": None,
                                            "min_length": None,
                                            "max_length": None,
                                            "parameters": {
                                                "added": {},
                                                "changed": {
                                                    "regex": None,
                                                    "min_length": None,
                                                    "max_length": None,
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
                    NEW_KIND: {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "value": {
                                        "added": {},
                                        "changed": {
                                            "regex": None,
                                            "min_length": None,
                                            "max_length": None,
                                            "parameters": {
                                                "added": {},
                                                "changed": {
                                                    "regex": None,
                                                    "min_length": None,
                                                    "max_length": None,
                                                },
                                                "removed": {},
                                            },
                                        },
                                        "removed": {},
                                    },
                                    "number": {
                                        "added": {},
                                        "changed": {
                                            "parameters": {
                                                "added": {},
                                                "changed": {
                                                    "min_value": None,
                                                    "max_value": None,
                                                },
                                                "removed": {},
                                            },
                                        },
                                        "removed": {},
                                    },
                                    "assigned_number": {
                                        "added": {},
                                        "changed": {
                                            "parameters": {
                                                "added": {},
                                                "changed": {
                                                    "start_range": None,
                                                    "end_range": None,
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
                },
                "removed": {},
            },
            "warnings": [
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingThingLegacy", "field": "value"}],
                    "message": "Use of 'max_length' on attributes is deprecated, use parameters instead",
                },
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingThingLegacy", "field": "value"}],
                    "message": "Use of 'min_length' on attributes is deprecated, use parameters instead",
                },
            ],
        }

    async def test_step02_load_schema_with_overrides(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        schema_step_02: dict[str, Any],
        regex_02: str,
        min_length_02: int,
        max_length_02: int,
    ) -> None:
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_02], branch=default_branch.name)
        assert not response.errors

        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        legacy_schema = updated_schema_branch.get_node(name=LEGACY_KIND, duplicate=False)
        self._validate_schema_value_parameters(
            schema=legacy_schema, regex=regex_02, min_length=min_length_02, max_length=max_length_02
        )

        new_schema = updated_schema_branch.get_node(name=NEW_KIND, duplicate=False)
        self._validate_schema_value_parameters(
            schema=new_schema, regex=regex_02, min_length=min_length_02, max_length=max_length_02
        )
        self._validate_schema_number_parameters(schema=new_schema, min_value=20, max_value=30)
        self._validate_schema_numberpool_parameters(schema=new_schema, start_range=50, end_range=1200)

    @staticmethod
    async def _pool_ranges(db: InfrahubDatabase) -> tuple[str, list[tuple[int, int, int | None]]]:
        pools = await NodeManager.query(
            db=db,
            schema=CoreNumberPool,
            filters={"node__value": NEW_KIND, "node_attribute__value": "assigned_number"},
            branch_agnostic=True,
        )
        assert len(pools) == 1
        pool = pools[0]
        ranges = await NumberPoolRepository(db=db).get_ranges(pool_id=pool.get_id())
        return pool.get_id(), [(item.start.value, item.end.value, item.allocation_weight.value) for item in ranges]

    @pytest.fixture(scope="class")
    async def thing_holding_a_number(
        self, db: InfrahubDatabase, default_branch: Branch, service: InfrahubServices
    ) -> Node:
        await run_schema_updated_workflow(service=service, branch=default_branch)
        thing = await Node.init(db=db, schema=NEW_KIND, branch=default_branch)
        await thing.new(db=db, value="regex02xx", number=25)
        await thing.save(db=db)
        return thing

    async def test_step03_range_excluding_a_held_value_is_refused(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        thing_holding_a_number: Node,
        schema_thing_legacy_02: dict[str, Any],
        schema_thing_03_excluding_held_value: dict[str, Any],
    ) -> None:
        assert thing_holding_a_number.get_attribute("assigned_number").value == 50

        response = await client.schema.load(
            schemas=[{"version": "1.0", "nodes": [schema_thing_legacy_02, schema_thing_03_excluding_held_value]}],
            branch=default_branch.name,
        )

        errors = str(response.errors)
        assert NEW_KIND in errors
        assert "assigned_number=50" in errors
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        self._validate_schema_numberpool_parameters(
            schema=schema_branch.get_node(name=NEW_KIND, duplicate=False), start_range=50, end_range=1200
        )
        assert (await self._pool_ranges(db=db))[1] == [(50, 1200, None)]

    async def test_step04_ranges_excluding_a_held_value_are_refused(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        thing_holding_a_number: Node,
        schema_thing_legacy_02: dict[str, Any],
        schema_thing_04_ranges_excluding_held_value: dict[str, Any],
    ) -> None:
        response = await client.schema.load(
            schemas=[
                {"version": "1.0", "nodes": [schema_thing_legacy_02, schema_thing_04_ranges_excluding_held_value]}
            ],
            branch=default_branch.name,
        )

        errors = str(response.errors)
        assert NEW_KIND in errors
        assert "assigned_number=50" in errors
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        self._validate_schema_numberpool_parameters(
            schema=schema_branch.get_node(name=NEW_KIND, duplicate=False), start_range=50, end_range=1200
        )
        assert (await self._pool_ranges(db=db))[1] == [(50, 1200, None)]

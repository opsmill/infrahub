from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.database import InfrahubDatabase
from tests.node_creation import create_and_save

from ..shared import load_schema
from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    PERSON_KIND,
    TestSchemaLifecycleBase,
)


class TestSchemaLifecycleAttributeBranch(TestSchemaLifecycleBase):
    @pytest.fixture(scope="class")
    async def branch_1(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch1")

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step_01: dict[str, Any]
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step_01)

        john = await create_and_save(db=db, schema=PERSON_KIND, name="John", unique_attr="abc", height=175)
        jane = await create_and_save(db=db, schema=PERSON_KIND, name="Jane", unique_attr="def", height=195)
        deleted_bob = await create_and_save(
            db=db, schema=PERSON_KIND, name="Deleted Bob", unique_attr="ghi", height=175, description="He's not here"
        )
        await deleted_bob.delete(db=db)
        renault = await create_and_save(
            db=db,
            schema=MANUFACTURER_KIND_01,
            name="renault",
            description="Groupe Renault is a French multinational automobile manufacturer",
        )
        megane = await create_and_save(
            db=db,
            schema=CAR_KIND,
            name="Megane",
            description="Renault Megane",
            color="#c93420",
            manufacturer=renault,
            owner=john,
        )
        clio = await create_and_save(
            db=db,
            schema=CAR_KIND,
            name="Clio",
            description="Renault Clio",
            color="#ff3420",
            manufacturer=renault,
            owner=jane,
        )
        deleted_car = await create_and_save(
            db=db, schema=CAR_KIND, name="Deleted", color="#aabbcc", manufacturer=renault, owner=john
        )
        await deleted_car.delete(db=db)

        objs = {
            "john": john.id,
            "deleted_bob": deleted_bob.id,
            "renault": renault.id,
            "megane": megane.id,
            "clio": clio.id,
        }

        return objs

    @pytest.fixture(scope="class")
    def schema_generic_01(self) -> dict[str, Any]:
        return {
            "name": "Thing",
            "namespace": "Testing",
            "include_in_menu": True,
            "attributes": [
                {"name": "unique_attr", "kind": "Text", "unique": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_person_base_with_generic(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        schema_person_base["inherit_from"] = ["TestingThing"]
        return schema_person_base

    @pytest.fixture(scope="class")
    def schema_person_02_more_fields(self, schema_person_base: dict[str, Any]) -> dict[str, Any]:
        """Add a new attribute and a new relationship"""
        updated_schema = {**schema_person_base}
        updated_schema["attributes"].append(
            {"name": "tax_id", "kind": "Number", "optional": True},
        )
        updated_schema["relationships"].append(
            {"name": "best_friend", "kind": "Generic", "optional": True, "peer": PERSON_KIND, "cardinality": "one"}
        )
        updated_schema["uniqueness_constraints"] = [["name__value", "height__value"]]
        updated_schema["order_by"] = ["name__value", "height__value"]
        updated_schema["display_labels"] = ["name__value", "tax_id__value", "height__value"]
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_person_03_unique_fields(self, schema_person_02_more_fields: dict[str, Any]) -> dict[str, Any]:
        """Make the new attribute unique, use the new relationship in node-level properties"""
        updated_schema = {**schema_person_02_more_fields}
        for attr in updated_schema["attributes"]:
            if attr["name"] == "tax_id":
                attr["unique"] = True
                attr["optional"] = False
        for rel in updated_schema["relationships"]:
            if rel["name"] == "best_friend":
                rel["optional"] = False
        updated_schema["human_friendly_id"] = ["name__value", "tax_id__value", "best_friend__unique_attr__value"]
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_person_04_rename_original_unique_fields(
        self, schema_person_03_unique_fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Rename the name attribute"""
        updated_schema = {**schema_person_03_unique_fields}
        for attr in updated_schema["attributes"]:
            if attr["name"] == "name":
                attr["name"] = "real_name"
        updated_schema.pop("human_friendly_id", None)
        updated_schema.pop("uniqueness_constraints", None)
        updated_schema.pop("order_by", None)
        updated_schema.pop("display_labels", None)
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_person_05_delete_original_unique_fields(
        self, schema_person_04_rename_original_unique_fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Delete the name attribute"""
        updated_schema = {**schema_person_04_rename_original_unique_fields}
        for attr in updated_schema["attributes"]:
            if attr["name"] == "real_name":
                attr["state"] = "absent"
        updated_schema.pop("human_friendly_id", None)
        updated_schema.pop("uniqueness_constraints", None)
        updated_schema.pop("order_by", None)
        updated_schema.pop("display_labels", None)
        updated_schema["display_label"] = "{{ tax_id__value }}"
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_generic_06_delete_unique_field(self, schema_generic_01: dict[str, Any]) -> dict[str, Any]:
        """Delete the unique attribute"""
        updated_schema = {**schema_generic_01}
        for attr in updated_schema["attributes"]:
            if attr["name"] == "unique_attr":
                attr["state"] = "absent"
        updated_schema.pop("human_friendly_id", None)
        updated_schema.pop("uniqueness_constraints", None)
        updated_schema.pop("order_by", None)
        updated_schema.pop("display_labels", None)
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_person_06_delete_unique_generic_field(
        self, schema_person_05_delete_original_unique_fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the human friendly ID to remove the deleted unique_attr field"""
        updated_schema = {**schema_person_05_delete_original_unique_fields}
        # has to be updated manually
        updated_schema["human_friendly_id"] = ["tax_id__value"]
        return updated_schema

    @pytest.fixture(scope="class")
    def schema_step_01(
        self,
        schema_generic_01: dict[str, Any],
        schema_car_base: dict[str, Any],
        schema_person_base_with_generic: dict[str, Any],
        schema_manufacturer_base: dict[str, Any],
        schema_tag_base: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "generics": [schema_generic_01],
            "nodes": [schema_person_base_with_generic, schema_car_base, schema_manufacturer_base, schema_tag_base],
        }

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_person_02_more_fields: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_02_more_fields],
        }

    @pytest.fixture(scope="class")
    def schema_step_03(self, schema_person_03_unique_fields: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_03_unique_fields],
        }

    @pytest.fixture(scope="class")
    def schema_step_04(self, schema_person_04_rename_original_unique_fields: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_04_rename_original_unique_fields],
        }

    @pytest.fixture(scope="class")
    def schema_step_05(self, schema_person_05_delete_original_unique_fields: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_05_delete_original_unique_fields],
        }

    @pytest.fixture(scope="class")
    def schema_step_06(
        self,
        schema_person_06_delete_unique_generic_field: dict[str, Any],
        schema_generic_06_delete_unique_field: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": "1.0",
            "nodes": [schema_person_06_delete_unique_generic_field],
            "generics": [schema_generic_06_delete_unique_field],
        }

    async def test_step01_baseline_backend(
        self, db: InfrahubDatabase, initial_dataset: dict[str, str], branch_1: Branch
    ) -> None:
        # Check schema properties
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_1)
        # check that unique attribute is correctly synced to uniqueness constraints
        person_schema = schema_branch.get(name=PERSON_KIND)
        assert person_schema.uniqueness_constraints == [["name__value"]]
        generic_schema = schema_branch.get(name="TestingThing")
        assert generic_schema.uniqueness_constraints == [["unique_attr__value"]]

        persons = await registry.manager.query(db=db, schema=PERSON_KIND, branch=branch_1.name)
        assert len(persons) == 2

    async def test_step02_check_more_fields(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_02: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step_02], branch=branch_1.name)
        assert success, response.get("errors") if response else None
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {"tax_id": None},
                                "changed": {},
                                "removed": {},
                            },
                            "relationships": {
                                "added": {"best_friend": None},
                                "changed": {},
                                "removed": {},
                            },
                            "uniqueness_constraints": None,
                            "order_by": None,
                            "display_label": None,
                            "display_labels": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingPerson", "field": None}],
                    "message": "display_labels are deprecated, use display_label instead",
                }
            ],
        }

    async def test_step02_load_more_fields(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_02: dict[str, Any],
    ) -> None:
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_02], branch=branch_1.name)
        assert not response.errors

        # Check if the branch has been properly updated
        branches = await client.branch.all()
        assert branches[branch_1.name].has_schema_changes is True

        # Ensure that we can query the nodes with the new schema in BRANCH1
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"name__value": "John"}, branch=branch_1.name
        )
        assert len(persons) == 1
        john = persons[0]
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"name__value": "Jane"}, branch=branch_1.name
        )
        assert len(persons) == 1
        jane = persons[0]

        john.tax_id.value = 9999
        jane.tax_id.value = 9998
        await john.best_friend.update(db=db, data=jane)
        await john.save(db=db)
        await jane.save(db=db)

    async def test_step03_check_unique_fields(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_03: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step_03], branch=branch_1.name)
        assert success, response.get("errors") if response else None
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "tax_id": {
                                        "added": {},
                                        "removed": {},
                                        "changed": {
                                            "optional": None,
                                            "unique": None,
                                        },
                                    }
                                },
                                "removed": {},
                            },
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "best_friend": {
                                        "added": {},
                                        "removed": {},
                                        "changed": {
                                            "optional": None,
                                            "min_count": None,
                                        },
                                    }
                                },
                                "removed": {},
                            },
                            "human_friendly_id": None,
                            "uniqueness_constraints": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingPerson", "field": None}],
                    "message": "display_labels are deprecated, use display_label instead",
                }
            ],
        }

    async def test_step03_load_unique_fields(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_03: dict[str, Any],
    ) -> None:
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_03], branch=branch_1.name)
        assert not response.errors

        # Check if the branch has been properly updated
        branches = await client.branch.all()
        assert branches[branch_1.name].has_schema_changes is True

        # Check schema properties
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_1)
        updated_person_schema = schema_branch.get(name=PERSON_KIND)
        assert updated_person_schema.uniqueness_constraints
        unique_constraint_sets = frozenset(tuple(uc) for uc in updated_person_schema.uniqueness_constraints)
        assert unique_constraint_sets == frozenset(
            [
                ("name__value", "height__value"),
                ("name__value",),
                ("tax_id__value",),
                ("name__value", "tax_id__value", "best_friend"),
            ]
        )
        assert updated_person_schema.human_friendly_id == [
            "name__value",
            "tax_id__value",
            "best_friend__unique_attr__value",
        ]
        assert updated_person_schema.display_labels == ["name__value", "tax_id__value", "height__value"]
        assert updated_person_schema.order_by == ["name__value", "height__value"]

    async def test_step04_check_rename_name(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_04: dict[str, Any],
    ) -> None:
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND, branch=branch_1)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it
        for attr_dict in schema_step_04["nodes"][0]["attributes"]:
            if attr_dict["name"] == "real_name":
                attr_dict["id"] = attr.id

        # Update the display label since the old one is invalid now
        schema_step_04["nodes"][0]["display_label"] = "real_name__value"

        success, response = await client.schema.check(schemas=[schema_step_04], branch=branch_1.name)
        assert success, response.get("errors") if response else None
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "real_name": {
                                        "added": {},
                                        "removed": {},
                                        "changed": {
                                            "name": None,
                                        },
                                    }
                                },
                                "removed": {},
                            },
                            "human_friendly_id": None,
                            "uniqueness_constraints": None,
                            "display_label": None,
                            "display_labels": None,
                            "order_by": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step04_load_renamed_fields(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_04: dict[str, Any],
    ) -> None:
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND, branch=branch_1)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it
        for attr_dict in schema_step_04["nodes"][0]["attributes"]:
            if attr_dict["name"] == "real_name":
                attr_dict["id"] = attr.id

        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_04], branch=branch_1.name)
        assert not response.errors

        # Check schema properties
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_1)
        updated_person_schema = schema_branch.get(name=PERSON_KIND)
        assert updated_person_schema.uniqueness_constraints
        unique_constraint_sets = frozenset(tuple(uc) for uc in updated_person_schema.uniqueness_constraints)
        assert unique_constraint_sets == frozenset(
            [
                ("real_name__value", "height__value"),
                ("real_name__value",),
                ("tax_id__value",),
                ("real_name__value", "tax_id__value", "best_friend"),
            ]
        )
        assert updated_person_schema.human_friendly_id == [
            "real_name__value",
            "tax_id__value",
            "best_friend__unique_attr__value",
        ]
        assert updated_person_schema.display_labels == ["real_name__value", "tax_id__value", "height__value"]
        assert updated_person_schema.order_by == ["real_name__value", "height__value"]

    async def test_step05_check_remove_original_unique(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_05: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step_05], branch=branch_1.name)
        assert success, response.get("errors") if response else None
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    # b/c there is now a uniqueness_constraint that is just height__value,
                                    # so the height attribute is automatically set to unique as well
                                    "height": {
                                        "added": {},
                                        "changed": {"unique": None},
                                        "removed": {},
                                    }
                                },
                                "removed": {"real_name": None},
                            },
                            "human_friendly_id": None,
                            "uniqueness_constraints": None,
                            "display_label": None,
                            "display_labels": None,
                            "order_by": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step05_load_remove_original_unique(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_05: dict[str, Any],
    ) -> None:
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_05], branch=branch_1.name)
        assert not response.errors

        # Check schema properties
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_1)
        updated_person_schema = schema_branch.get(name=PERSON_KIND)
        assert updated_person_schema.uniqueness_constraints
        unique_constraint_sets = frozenset(tuple(uc) for uc in updated_person_schema.uniqueness_constraints)
        assert unique_constraint_sets == frozenset(
            [
                ("height__value",),
                ("tax_id__value",),
                ("tax_id__value", "best_friend"),
            ]
        )
        assert updated_person_schema.human_friendly_id == [
            "tax_id__value",
            "best_friend__unique_attr__value",
        ]
        assert updated_person_schema.display_labels == ["tax_id__value", "height__value"]
        assert updated_person_schema.order_by == ["height__value"]

    async def test_step06_check_remove_unique_attr_from_generic(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_06: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step_06], branch=branch_1.name)
        assert success, response.get("errors") if response else None
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingThing": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {},
                                "removed": {"unique_attr": None},
                            },
                            "human_friendly_id": None,
                            "uniqueness_constraints": None,
                        },
                        "removed": {},
                    },
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {
                                    "unique_attr": {"added": {}, "changed": {"state": None}, "removed": {}},
                                },
                                "removed": {},
                            },
                            "human_friendly_id": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [],
        }

    async def test_step06_load_remove_unique_attr_from_generic(
        self,
        db: InfrahubDatabase,
        branch_1: Branch,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step_06: dict[str, Any],
    ) -> None:
        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step_06], branch=branch_1.name)
        assert not response.errors

        # Check schema properties
        schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch_1)
        updated_generic_schema = schema_branch.get(name="TestingThing")
        assert not updated_generic_schema.uniqueness_constraints

        updated_person_schema = schema_branch.get(name=PERSON_KIND)
        assert updated_person_schema.uniqueness_constraints
        unique_constraint_sets = frozenset(tuple(uc) for uc in updated_person_schema.uniqueness_constraints)
        assert unique_constraint_sets == frozenset(
            [
                ("height__value",),
                ("tax_id__value",),
                ("tax_id__value", "best_friend"),
            ]
        )
        assert updated_person_schema.human_friendly_id == [
            "tax_id__value",
        ]
        assert updated_person_schema.display_labels == ["tax_id__value", "height__value"]
        assert updated_person_schema.order_by == ["height__value"]

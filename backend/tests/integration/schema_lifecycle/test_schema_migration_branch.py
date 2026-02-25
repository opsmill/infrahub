from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.metadata.query.node_metadata import NodeMetadataDefaultBranchQuery
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount
from infrahub.core.query.node import MetadataOptions
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from infrahub.exceptions import InitializationError, SchemaNotFoundError

from ..shared import load_schema
from .shared import (
    CAR_KIND,
    MANUFACTURER_KIND_01,
    MANUFACTURER_KIND_03,
    PERSON_KIND,
    TAG_KIND,
    TestSchemaLifecycleBase,
)


class BranchState:
    def __init__(self) -> None:
        self._branch: Branch | None = None

    @property
    def branch(self) -> Branch:
        if self._branch:
            return self._branch
        raise InitializationError

    @branch.setter
    def branch(self, value: Branch) -> None:
        self._branch = value


state = BranchState()


class TestSchemaLifecycleBranch(TestSchemaLifecycleBase):
    @property
    def branch1(self) -> Branch:
        return state.branch

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self, db: InfrahubDatabase, initialize_registry: None, schema_step01: dict[str, Any], client: InfrahubClient
    ) -> dict[str, str]:
        await load_schema(db=db, schema=schema_step01)

        # Load data in the MAIN branch first
        john = await Node.init(schema=PERSON_KIND, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

        deleted_bob = await Node.init(schema=PERSON_KIND, db=db)
        await deleted_bob.new(db=db, name="Deleted Bob", height=175, description="He's not here")
        await deleted_bob.save(db=db)
        await deleted_bob.delete(db=db)

        renault = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await renault.new(
            db=db, name="renault", description="Groupe Renault is a French multinational automobile manufacturer"
        )
        await renault.save(db=db)

        megane = await Node.init(schema=CAR_KIND, db=db)
        await megane.new(
            db=db, name="Megane", description="Renault Megane", color="#c93420", manufacturer=renault, owner=john
        )
        await megane.save(db=db, user_id="megane-creator")

        clio = await Node.init(schema=CAR_KIND, db=db)
        await clio.new(
            db=db, name="Clio", description="Renault Clio", color="#ff3420", manufacturer=renault, owner=john
        )
        await clio.save(db=db)

        red = await Node.init(schema=TAG_KIND, db=db)
        await red.new(db=db, name="red", persons=[john])
        await red.save(db=db)

        # Create Branch1
        branch1 = await create_branch(db=db, branch_name="branch1")
        state.branch = branch1

        # Load data in BRANCH1
        richard = await Node.init(schema=PERSON_KIND, db=db, branch=branch1)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

        deleted_chuck = await Node.init(schema=PERSON_KIND, db=db, branch=branch1)
        await deleted_chuck.new(db=db, name="Deleted Chuck", height=175, description="He's not here")
        await deleted_chuck.save(db=db)
        await deleted_chuck.delete(db=db)

        mercedes = await Node.init(schema=MANUFACTURER_KIND_01, db=db, branch=branch1)
        await mercedes.new(
            db=db, name="mercedes", description="Mercedes-Benz, commonly referred to as Mercedes and sometimes as Benz"
        )
        await mercedes.save(db=db)

        glc = await Node.init(schema=CAR_KIND, db=db, branch=branch1)
        await glc.new(
            db=db, name="glc", description="Mecedes GLC", color="#3422eb", manufacturer=mercedes, owner=richard
        )
        await glc.save(db=db)

        green = await Node.init(schema=TAG_KIND, db=db, branch=branch1)
        await green.new(db=db, name="green", persons=[john, richard])
        await green.save(db=db)

        # Create Data in MAIN after BRANCH1 was created
        jane = await Node.init(schema=PERSON_KIND, db=db)
        await jane.new(db=db, name="Jane", height=165, description="The famous Jane Doe")
        await jane.save(db=db, user_id="jane-creator")

        honda = await Node.init(schema=MANUFACTURER_KIND_01, db=db)
        await honda.new(db=db, name="honda", description="Honda Motor Co., Ltd")
        await honda.save(db=db)

        accord = await Node.init(schema=CAR_KIND, db=db)
        await accord.new(
            db=db, name="accord", description="Honda Accord", color="#3443eb", manufacturer=honda, owner=jane
        )
        await accord.save(db=db)

        civic = await Node.init(schema=CAR_KIND, db=db)
        await civic.new(db=db, name="civic", description="Honda Civic", color="#c9eb34", manufacturer=honda, owner=jane)
        await civic.save(db=db)

        blue = await Node.init(schema=TAG_KIND, db=db)
        await blue.new(db=db, name="blue", cars=[accord, civic], persons=[jane])
        await blue.save(db=db, user_id="blue-creator")

        objs = {
            "john": john.id,
            "jane": jane.id,
            "richard": richard.id,
            "honda": honda.id,
            "renault": renault.id,
            "mercedes": mercedes.id,
            "accord": accord.id,
            "civic": civic.id,
            "megane": megane.id,
            "clio": clio.id,
            "glc": glc.id,
            "blue": blue.id,
            "red": red.id,
            "green": green.id,
        }

        return objs

    async def test_step01_baseline_backend(self, db: InfrahubDatabase, initial_dataset: dict[str, str]) -> None:
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, branch=self.branch1)
        assert len(persons) == 2

    async def test_step02_check_attr_add_rename(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step02: dict[str, Any],
    ) -> None:
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        success, response = await client.schema.check(schemas=[schema_step02], branch=self.branch1.name)
        assert success
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {"lastname": None},
                                "changed": {
                                    "firstname": {
                                        "added": {},
                                        "changed": {"name": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                            "uniqueness_constraints": None,
                            "human_friendly_id": None,
                        },
                        "removed": {},
                    },
                },
                "removed": {},
            },
            "warnings": [
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingCar", "field": None}],
                    "message": "default_filter is deprecated",
                }
            ],
        }

    async def test_step02_load_attr_add_rename(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step02: dict[str, Any],
    ) -> None:
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND, branch=self.branch1)
        attr = person_schema.get_attribute(name="name")

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        schema_step02["nodes"][0]["attributes"][0]["id"] = attr.id

        # Load the new schema and apply the migrations
        response = await client.schema.load(schemas=[schema_step02], branch=self.branch1.name)
        assert not response.errors

        # Check if the branch has been properly updated
        branches = await client.branch.all()
        assert branches[self.branch1.name].has_schema_changes is True

        # Ensure that we can query the nodes with the new schema in BRANCH1
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"firstname__value": "John"}, branch=self.branch1.name
        )
        assert len(persons) == 1
        john = persons[0]
        assert john.firstname.value == "John"  # type: ignore[attr-defined]

        # Set a value to the new attribute
        john.lastname.value = "Doe"  # type: ignore[attr-defined]
        await john.save(db=db)

        # And ensure that we can still query them with the original schema in MAIN
        persons = await registry.manager.query(db=db, schema=PERSON_KIND, filters={"name__value": "John"})
        assert len(persons) == 1
        john = persons[0]
        assert john.name.value == "John"  # type: ignore[attr-defined]

    async def test_step03_check(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step03: dict[str, Any],
    ) -> None:
        manufacturer_schema = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01, branch=self.branch1)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step03["nodes"][2]["name"] == "CarMaker"
        schema_step03["nodes"][2]["id"] = manufacturer_schema.id

        success, response = await client.schema.check(schemas=[schema_step03], branch=self.branch1.name)
        assert response == {
            "diff": {
                "added": {},
                "changed": {
                    "TestingCar": {
                        "added": {},
                        "changed": {
                            "relationships": {
                                "added": {},
                                "changed": {
                                    "manufacturer": {
                                        "added": {},
                                        "changed": {"peer": None},
                                        "removed": {},
                                    },
                                },
                                "removed": {},
                            },
                        },
                        "removed": {},
                    },
                    "TestingCarMaker": {
                        "added": {},
                        "changed": {
                            "label": None,
                            "name": None,
                        },
                        "removed": {},
                    },
                    "TestingPerson": {
                        "added": {},
                        "changed": {
                            "attributes": {
                                "added": {},
                                "changed": {},
                                "removed": {"height": None},
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
                    "kinds": [{"kind": "TestingCar", "field": None}],
                    "message": "default_filter is deprecated",
                }
            ],
        }
        assert success

    async def test_step03_load(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step03: dict[str, Any],
    ) -> None:
        manufacturer_schema = registry.schema.get_node_schema(name=MANUFACTURER_KIND_01, branch=self.branch1)
        person_schema = registry.schema.get_node_schema(name=PERSON_KIND, branch=self.branch1)
        height_attr_schema = person_schema.get_attribute(name="height")
        assert height_attr_schema.id

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step03["nodes"][2]["name"] == "CarMaker"
        schema_step03["nodes"][2]["id"] = manufacturer_schema.id

        response = await client.schema.load(schemas=[schema_step03], branch=self.branch1.name)
        assert not response.errors

        # Ensure that we can query the existing node with the new schema
        # person_schema = registry.schema.get(name=PERSON_KIND)
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"firstname__value": "John"}, branch=self.branch1.name
        )
        assert len(persons) == 1
        john = persons[0]
        assert not hasattr(john, "height")

        updated_height_attr_schema = await registry.manager.get_one(
            db=db, branch=self.branch1.name, id=height_attr_schema.id
        )
        assert updated_height_attr_schema is None

        manufacturers = await registry.manager.query(
            db=db, schema=MANUFACTURER_KIND_03, filters={"name__value": "renault"}, branch=self.branch1.name
        )
        assert len(manufacturers) == 1
        renault = manufacturers[0]
        renault_cars = await renault.cars.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(renault_cars) == 2

    async def test_rebase(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        admin_account: CoreAccount,
    ) -> None:
        time_before_rebase = Timestamp()
        branch = await client.branch.rebase(branch_name=self.branch1.name)
        assert branch
        time_after_rebase = Timestamp()

        person_schema = registry.schema.get_node_schema(name=PERSON_KIND, branch=default_branch)
        height_attr_schema = person_schema.get_attribute(name="height")
        assert height_attr_schema.id

        # Validate that all data added to main after the creation of the branch has been migrated properly
        updated_height_attr_schema = await registry.manager.get_one(
            db=db, branch=self.branch1.name, id=height_attr_schema.id
        )
        assert updated_height_attr_schema is None
        persons = await registry.manager.query(
            db=db, schema=PERSON_KIND, filters={"firstname__value": "Jane"}, branch=self.branch1.name
        )
        assert len(persons) == 1
        jane = persons[0]
        assert not hasattr(jane, "height")

        manufacturers = await registry.manager.query(
            db=db, schema=MANUFACTURER_KIND_03, filters={"name__value": "honda"}, branch=self.branch1.name
        )
        assert len(manufacturers) == 1
        honda = manufacturers[0]
        honda_cars = await honda.cars.get_peers(db=db)  # type: ignore[attr-defined]
        assert len(honda_cars) == 2

        # Validate metadata on nodes modified by rebase migrations
        # Jane was created in main after branch1 was created, so she was migrated during rebase
        # The migration added the 'lastname' attribute and removed 'height'
        updated_branch_1 = await Branch.get_by_name(db=db, name=self.branch1.name)
        jane_with_metadata = await NodeManager.get_one(
            db=db,
            id=initial_dataset["jane"],
            branch=updated_branch_1,
            include_metadata=MetadataQueryOptions(
                node_level=MetadataOptions.USER_TIMESTAMPS,
                attribute_level=MetadataOptions.USER_TIMESTAMPS,
            ),
        )

        # Node should have been updated during the rebase migration
        assert jane_with_metadata._get_created_at() < time_before_rebase
        assert jane_with_metadata._get_created_by() == "jane-creator"
        assert time_before_rebase < jane_with_metadata._get_updated_at() < time_after_rebase
        assert jane_with_metadata._get_updated_by() == admin_account.id

        # The new 'lastname' attribute should have been created during the migration
        lastname_attr = jane_with_metadata.get_attribute(name="lastname")
        assert lastname_attr._get_created_at() < time_after_rebase
        assert lastname_attr._get_created_at() > time_before_rebase
        assert lastname_attr._get_created_by() == admin_account.id
        assert lastname_attr._get_updated_at() == lastname_attr._get_created_at()
        assert lastname_attr._get_updated_by() == admin_account.id

    async def test_step04_check(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step04: dict[str, Any],
    ) -> None:
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND, branch=self.branch1)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step04["nodes"][3]["name"] == "Tag"
        schema_step04["nodes"][3]["id"] = tag_schema.id

        success, response = await client.schema.check(schemas=[schema_step04], branch=self.branch1.name)

        assert response == {
            "diff": {"added": {}, "changed": {}, "removed": {"TestingTag": None}},
            "warnings": [
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingCar", "field": None}],
                    "message": "default_filter is deprecated",
                }
            ],
        }
        assert success

    async def test_step04_load(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step04: dict[str, Any],
    ) -> None:
        tag_schema = registry.schema.get_node_schema(name=TAG_KIND, branch=self.branch1)

        # Insert the ID of the attribute name into the schema in order to rename it firstname
        assert schema_step04["nodes"][3]["name"] == "Tag"
        schema_step04["nodes"][3]["id"] = tag_schema.id

        response = await client.schema.load(schemas=[schema_step04], branch=self.branch1.name)
        assert not response.errors

        assert registry.schema.has(name=TAG_KIND) is True
        # FIXME after loading the new schema, TestingTag is still present in the branch, need to investigate
        # assert registry.schema.has(name=TAG_KIND, branch=self.branch1) is False

        # check that tag attributes/relationships are deleted on branch
        attr_schemas = await NodeManager.query(
            db=db, branch=self.branch1, schema="SchemaAttribute", filters={"node__id": tag_schema.id}
        )
        assert len(attr_schemas) == 0
        rel_schemas = await NodeManager.query(
            db=db, branch=self.branch1, schema="SchemaRelationship", filters={"node__id": tag_schema.id}
        )
        assert len(rel_schemas) == 0
        # check that tag attributes/relationships still exist on main
        attr_schemas = await NodeManager.query(db=db, schema="SchemaAttribute", filters={"node__id": tag_schema.id})
        assert len(attr_schemas) == 1
        assert {a.name.value for a in attr_schemas} == {"name"}
        rel_schemas = await NodeManager.query(db=db, schema="SchemaRelationship", filters={"node__id": tag_schema.id})
        assert len(rel_schemas) == 5
        assert {r.name.value for r in rel_schemas} == {
            "cars",
            "persons",
            "profiles",
            "subscriber_of_groups",
            "member_of_groups",
        }

        tags = await registry.manager.query(db=db, schema=TAG_KIND)
        assert len(tags) == 2

    async def test_step05_check(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step05: dict[str, Any],
    ) -> None:
        success, response = await client.schema.check(schemas=[schema_step05], branch=self.branch1.name)

        assert response == {
            "diff": {
                "added": {},
                "removed": {},
                "changed": {
                    "TestingCar": {
                        "added": {},
                        "changed": {
                            "generate_profile": None,
                        },
                        "removed": {},
                    },
                },
            },
            "warnings": [
                {
                    "type": "deprecation",
                    "kinds": [{"kind": "TestingCar", "field": None}],
                    "message": "default_filter is deprecated",
                }
            ],
        }
        assert success

    async def test_step05_load(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step05: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_step05], branch=self.branch1.name)
        assert not response.errors

        with pytest.raises(SchemaNotFoundError):
            registry.schema.get(name=f"Profile{CAR_KIND}", branch=self.branch1, check_branch_only=True)
        car_schema = registry.schema.get(name=CAR_KIND, branch=self.branch1, duplicate=False)
        assert "profiles" in car_schema.relationship_names

    async def test_step05_merge(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        initial_dataset: dict[str, str],
        schema_step06: dict[str, Any],
        schema_interior_base: dict[str, Any],
        admin_account: CoreAccount,
    ) -> None:
        response = await client.schema.load(schemas=[schema_step06], branch=self.branch1.name)
        assert not response.errors

        time_before_merge = Timestamp()
        await client.branch.merge(branch_name=self.branch1.name)
        time_after_merge = Timestamp()

        updated_branch = await Branch.get_by_name(name=self.branch1.name, db=db)
        updated_schema_default = await registry.schema.load_schema_from_db(db=db)
        default_interiors_schema = updated_schema_default.get(name="TestingInterior", duplicate=False)
        assert default_interiors_schema.attribute_names == ["material"]
        assert "cars" in default_interiors_schema.relationship_names
        updated_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=updated_branch)
        updated_interiors_schema = updated_schema_branch.get(name="TestingInterior", duplicate=False)
        assert updated_interiors_schema.attribute_names == ["material"]
        assert "cars" in updated_interiors_schema.relationship_names

        # Validate metadata on deleted blue tag using NodeMetadataDefaultBranchQuery
        # The blue tag was deleted during the merge because TestingTag was removed in schema_step04
        default_branch = registry.get_branch_from_registry(branch=registry.default_branch)
        blue_metadata_query = await NodeMetadataDefaultBranchQuery.init(
            db=db, branch=default_branch, node_uuids=[initial_dataset["blue"]]
        )
        await blue_metadata_query.execute(db=db)
        blue_metadatas = blue_metadata_query.get_metadatas()

        assert len(blue_metadatas) == 1
        blue_metadata = blue_metadatas[0]

        # Verify the blue tag is marked as deleted
        assert blue_metadata.is_deleted is True
        assert blue_metadata.uuid == initial_dataset["blue"]
        assert blue_metadata.kind == TAG_KIND

        # Verify metadata timestamps - created before merge, updated during merge
        assert blue_metadata.created_at is not None
        assert blue_metadata.created_at < time_before_merge
        assert blue_metadata.created_by == "blue-creator"
        assert blue_metadata.updated_at is not None
        assert time_before_merge < blue_metadata.updated_at < time_after_merge
        assert blue_metadata.updated_by == admin_account.id

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)

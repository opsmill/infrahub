import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType
from infrahub.core.node import Node
from infrahub.core.relationship.constraints.profiles_kind import RelationshipProfilesKindConstraint
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.test_app import TestInfrahubApp


class TestRelationshipProfilesKindConstraint(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    def schema(self, default_branch: Branch, register_internal_schema: SchemaBranch) -> None:
        schema_dict = {
            "generics": [
                {
                    "name": "GenericSpaceObject",
                    "namespace": "Test",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "mass", "kind": "Number", "optional": True},
                        {"name": "albedo", "kind": "Number", "optional": True},
                    ],
                },
                {
                    "name": "OtherGeneric",
                    "namespace": "Test",
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "smell", "kind": "Text", "optional": True},
                    ],
                },
            ],
            "nodes": [
                {
                    "name": "Ship",
                    "namespace": "Test",
                    "default_filter": "name__value",
                    "display_labels": ["name__value", "color__value"],
                    "inherit_from": ["TestGenericSpaceObject"],
                    "branch": BranchSupportType.AWARE.value,
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {"name": "nbr_seats", "kind": "Number", "optional": True},
                        {"name": "color", "kind": "Text", "optional": True},
                    ],
                },
            ],
        }

        schema_root = SchemaRoot(**schema_dict)
        return registry.schema.register_schema(schema=schema_root, branch=registry.default_branch)

    @pytest.fixture
    async def ship_one(self, db: InfrahubDatabase, schema) -> Node:
        ship = await Node.init(db=db, schema="TestShip")
        await ship.new(db=db, name="Nostromo", color="grimy black")
        await ship.save(db=db)
        return ship

    @pytest.fixture(scope="class")
    async def space_object_profile(self, db: InfrahubDatabase, schema) -> Node:
        space_profile = await Node.init(db=db, schema="ProfileTestGenericSpaceObject")
        await space_profile.new(db=db, profile_name="small space thing", profile_priority=500, mass=100)
        await space_profile.save(db=db)
        return space_profile

    @pytest.fixture(scope="class")
    async def ship_profile(self, db: InfrahubDatabase, schema) -> Node:
        ship_profile = await Node.init(db=db, schema="ProfileTestShip")
        await ship_profile.new(db=db, profile_name="cool ship", profile_priority=400, color="very matte black")
        await ship_profile.save(db=db)
        return ship_profile

    async def test_empty_profiles_allowed(self, db: InfrahubDatabase, ship_one: Node, ship_profile: Node):
        ship_schema = registry.schema.get_node_schema(name="TestShip", duplicate=False)

        constraint = RelationshipProfilesKindConstraint(db=db)
        await constraint.check(relm=ship_one.profiles, node_schema=ship_schema)

    async def test_profile_for_schema_allowed(self, db: InfrahubDatabase, ship_one: Node, ship_profile: Node):
        ship_schema = registry.schema.get_node_schema(name="TestShip", duplicate=False)

        constraint = RelationshipProfilesKindConstraint(db=db)
        await ship_one.profiles.add(db=db, data=ship_profile)
        await ship_one.profiles.resolve(db=db)

        await constraint.check(relm=ship_one.profiles, node_schema=ship_schema)

    async def test_generic_profile_allowed(self, db: InfrahubDatabase, ship_one: Node, space_object_profile: Node):
        ship_schema = registry.schema.get_node_schema(name="TestShip", duplicate=False)

        constraint = RelationshipProfilesKindConstraint(db=db)
        await ship_one.profiles.add(db=db, data=space_object_profile)
        await ship_one.profiles.resolve(db=db)

        await constraint.check(relm=ship_one.profiles, node_schema=ship_schema)

    async def test_wrong_profile_not_allowed(self, db: InfrahubDatabase, ship_one: Node):
        wrong_profile = await Node.init(db=db, schema="ProfileTestOtherGeneric")
        await wrong_profile.new(db=db, profile_name="something", profile_priority=400, smell="not good")
        await wrong_profile.save(db=db)
        ship_schema = registry.schema.get_node_schema(name="TestShip", duplicate=False)

        constraint = RelationshipProfilesKindConstraint(db=db)
        await ship_one.profiles.add(db=db, data=wrong_profile)
        await ship_one.profiles.resolve(db=db)

        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=ship_one.profiles, node_schema=ship_schema)

        assert "is of kind ProfileTestOtherGeneric" in exc.value.message
        assert "only ['ProfileTestGenericSpaceObject', 'ProfileTestShip'] are allowed" in exc.value.message

    async def test_generic_profile_not_allowed_when_generic_generate_profile_is_false(
        self, db: InfrahubDatabase, ship_one: Node, space_object_profile: Node
    ):
        ship_schema = registry.schema.get_node_schema(name="TestShip", duplicate=False)
        generic_schema = registry.schema.get(name="TestGenericSpaceObject", duplicate=False)
        generic_schema.generate_profile = False

        constraint = RelationshipProfilesKindConstraint(db=db)
        await ship_one.profiles.add(db=db, data=space_object_profile)
        await ship_one.profiles.resolve(db=db)

        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=ship_one.profiles, node_schema=ship_schema)

        assert "is of kind ProfileTestGenericSpaceObject" in exc.value.message
        assert "only ['ProfileTestShip'] are allowed" in exc.value.message

    async def test_profile_not_allowed_when_generate_profile_is_false(
        self, db: InfrahubDatabase, ship_one: Node, space_object_profile: Node
    ):
        ship_schema = registry.schema.get_node_schema(name="TestShip", duplicate=False)
        ship_schema.generate_profile = False

        constraint = RelationshipProfilesKindConstraint(db=db)
        await ship_one.profiles.add(db=db, data=space_object_profile)
        await ship_one.profiles.resolve(db=db)

        with pytest.raises(ValidationError, match="TestShip does not allow profiles"):
            await constraint.check(relm=ship_one.profiles, node_schema=ship_schema)

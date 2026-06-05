"""Integration tests verifying NodeUniquenessConstraintsUpdateMigration is triggered.

and runs correctly during an end-to-end schema load when uniqueness constraints change.

"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.helpers.db_validation import assert_attribute_absent, assert_attribute_path_status
from tests.integration.profiles.validation import assert_no_virtual_schema_relationships_in_db

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


CAR_KIND = "TestingCar"
PROFILE_CAR_KIND = "ProfileTestingCar"


class TestUniquenessConstraintMigrationAddToConstraint(TestSchemaLifecycleBase):
    """Verify that adding an attribute to a uniqueness constraint triggers the migration.

    that removes that attribute from existing profile nodes.

    """

    @pytest.fixture(scope="class")
    def schema_car_nbr_seats_no_constraint(self) -> dict[str, Any]:
        """Car schema — nbr_seats optional, not in any uniqueness constraint. Profiles include nbr_seats."""
        return {
            "name": "Car",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Car",
            "attributes": [
                {"name": "name", "kind": "Text", "unique": True},
                {"name": "nbr_seats", "kind": "Number", "optional": True},
                {"name": "color", "kind": "Text", "optional": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_car_nbr_seats_in_constraint(self, schema_car_nbr_seats_no_constraint: dict[str, Any]) -> dict[str, Any]:
        """Car schema — nbr_seats in a uniqueness constraint. Profiles should exclude nbr_seats."""
        schema = copy.deepcopy(schema_car_nbr_seats_no_constraint)
        schema["uniqueness_constraints"] = [["name__value", "nbr_seats__value"]]
        return schema

    @pytest.fixture(scope="class")
    def schema_step_01(self, schema_car_nbr_seats_no_constraint: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_car_nbr_seats_no_constraint]}

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_car_nbr_seats_in_constraint: dict[str, Any]) -> dict[str, Any]:
        return {"version": "1.0", "nodes": [schema_car_nbr_seats_in_constraint]}

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_step_01: dict[str, Any],
    ) -> None:
        await load_schema(db=db, schema=schema_step_01)
        profile = await Node.init(schema=PROFILE_CAR_KIND, db=db)
        await profile.new(db=db, profile_name="car-profile-1", nbr_seats=4)
        await profile.save(db=db)

    async def test_step01_nbr_seats_active_in_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: None,
    ) -> None:
        """Baseline: profile's nbr_seats attribute is active and readable before any constraint change."""
        await assert_attribute_path_status(
            db=db,
            node_label=PROFILE_CAR_KIND,
            attr_name="nbr_seats",
            branch_name=default_branch.name,
            expected_status="active",
        )

        profiles = await registry.manager.query(
            db=db, schema=PROFILE_CAR_KIND, filters={"profile_name__value": "car-profile-1"}
        )
        assert len(profiles) == 1
        assert hasattr(profiles[0], "nbr_seats")
        assert profiles[0].nbr_seats.value == 4

    async def test_step02_check_detects_uniqueness_constraint_change(
        self,
        client: InfrahubClient,
        initial_dataset: None,
        schema_step_02: dict[str, Any],
    ) -> None:
        """Schema check reports the uniqueness_constraints field as changed."""
        success, response = await client.schema.check(schemas=[schema_step_02])
        assert success
        assert response["diff"]["changed"][CAR_KIND]["changed"]["uniqueness_constraints"] is None

    async def test_step02_load_triggers_migration_removing_nbr_seats_from_profile(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: None,
        schema_step_02: dict[str, Any],
    ) -> None:
        """Loading a schema that adds nbr_seats to a uniqueness constraint triggers the migration.

        that deletes nbr_seats from existing profile nodes.

        """
        response = await client.schema.load(schemas=[schema_step_02])
        assert not response.errors

        await assert_attribute_path_status(
            db=db,
            node_label=PROFILE_CAR_KIND,
            attr_name="nbr_seats",
            branch_name=default_branch.name,
            expected_status="deleted",
        )

        profiles = await registry.manager.query(
            db=db, schema=PROFILE_CAR_KIND, filters={"profile_name__value": "car-profile-1"}
        )
        assert len(profiles) == 1
        assert not hasattr(profiles[0], "nbr_seats")

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
        await assert_no_virtual_schema_relationships_in_db(db=db)


class TestUniquenessConstraintMigrationRemoveFromConstraint(TestSchemaLifecycleBase):
    """Verify that removing an attribute from a uniqueness constraint triggers the migration.

    that adds that attribute back to existing profile nodes.

    """

    @pytest.fixture(scope="class")
    def schema_car_compound_constraint_only(self) -> dict[str, Any]:
        """Car schema — only a compound uniqueness constraint on (name, nbr_seats).

        name has no individual unique flag, so nbr_seats is excluded from profiles.
        """
        return {
            "name": "Car",
            "namespace": "Testing",
            "include_in_menu": True,
            "label": "Car",
            "uniqueness_constraints": [["name__value", "nbr_seats__value"]],
            "attributes": [
                {"name": "name", "kind": "Text"},
                {"name": "nbr_seats", "kind": "Number", "optional": True},
                {"name": "color", "kind": "Text", "optional": True},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_car_name_unique_no_compound(self, schema_car_compound_constraint_only: dict[str, Any]) -> dict[str, Any]:
        """Car schema — name is individually unique, no compound constraint.

        nbr_seats is free to be included in profiles.
        """
        schema = copy.deepcopy(schema_car_compound_constraint_only)
        schema["uniqueness_constraints"] = []
        schema["attributes"][0]["unique"] = True
        return schema

    @pytest.fixture(scope="class")
    def schema_step_01(self, schema_car_compound_constraint_only: dict[str, Any]) -> dict[str, Any]:
        """Initial schema: nbr_seats IS in the uniqueness constraint (profiles exclude it)."""
        return {"version": "1.0", "nodes": [schema_car_compound_constraint_only]}

    @pytest.fixture(scope="class")
    def schema_step_02(self, schema_car_name_unique_no_compound: dict[str, Any]) -> dict[str, Any]:
        """Updated schema: nbr_seats removed from the compound constraint (profiles should include it)."""
        return {"version": "1.0", "nodes": [schema_car_name_unique_no_compound]}

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_step_01: dict[str, Any],
    ) -> None:
        await load_schema(db=db, schema=schema_step_01)
        # nbr_seats is excluded from profiles because it is in the uniqueness constraint
        profile = await Node.init(schema=PROFILE_CAR_KIND, db=db)
        await profile.new(db=db, profile_name="car-profile-1")
        await profile.save(db=db)

    async def test_step01_nbr_seats_absent_from_profile(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: None,
    ) -> None:
        """Baseline: profile has no nbr_seats attribute because it is in the uniqueness constraint."""
        await assert_attribute_absent(
            db=db,
            node_label=PROFILE_CAR_KIND,
            attr_name="nbr_seats",
            branch_name=default_branch.name,
        )

        profiles = await registry.manager.query(
            db=db, schema=PROFILE_CAR_KIND, filters={"profile_name__value": "car-profile-1"}
        )
        assert len(profiles) == 1
        assert not hasattr(profiles[0], "nbr_seats")

    async def test_step02_check_detects_uniqueness_constraint_change(
        self,
        client: InfrahubClient,
        initial_dataset: None,
        schema_step_02: dict[str, Any],
    ) -> None:
        """Schema check reports the uniqueness_constraints field as changed."""
        success, response = await client.schema.check(schemas=[schema_step_02])
        assert success
        assert response["diff"]["changed"][CAR_KIND]["changed"]["uniqueness_constraints"] is None

    async def test_step02_load_triggers_migration_adding_nbr_seats_to_profile(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initial_dataset: None,
        schema_step_02: dict[str, Any],
    ) -> None:
        """Loading a schema that removes nbr_seats from a uniqueness constraint triggers the migration.

        that adds nbr_seats to existing profile nodes.

        """
        response = await client.schema.load(schemas=[schema_step_02])
        assert not response.errors

        await assert_attribute_path_status(
            db=db,
            node_label=PROFILE_CAR_KIND,
            attr_name="nbr_seats",
            branch_name=default_branch.name,
            expected_status="active",
        )

        profiles = await registry.manager.query(
            db=db, schema=PROFILE_CAR_KIND, filters={"profile_name__value": "car-profile-1"}
        )
        assert len(profiles) == 1

        profile = profiles[0]
        assert hasattr(profile, "nbr_seats")
        assert profile.nbr_seats.value is None

        profile.nbr_seats.value = 87
        await profile.save(db=db)

        profiles = await registry.manager.query(
            db=db, schema=PROFILE_CAR_KIND, filters={"profile_name__value": "car-profile-1"}
        )
        assert len(profiles) == 1

        profile = profiles[0]
        assert hasattr(profile, "nbr_seats")
        assert profile.nbr_seats.value == 87

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
        await assert_no_virtual_schema_relationships_in_db(db=db)

from copy import deepcopy

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase
from infrahub.lock_getter import (
    _get_kinds_to_lock_on_object_mutation,
    _hash,
    _should_kind_be_locked_on_any_branch,
    get_lock_names_on_object_mutation,
)
from tests.helpers.test_app import TestInfrahubApp
from tests.node_creation import create_and_save


class TestGetKindsLock(TestInfrahubApp):
    async def test_get_kinds_lock(
        self,
        db: InfrahubDatabase,
        default_branch,
        register_core_models_schema,
        client,
    ):
        # CoreCredential has no uniqueness_constraint, but generic CorePasswordCredential has one
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        assert _get_kinds_to_lock_on_object_mutation(kind="CorePasswordCredential", schema_branch=schema_branch) == [
            "CoreCredential"
        ]

        # 3 generics but only GenericAccount has a uniqueness_constraint
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        assert _get_kinds_to_lock_on_object_mutation(kind="CoreAccount", schema_branch=schema_branch) == [
            "CoreGenericAccount"
        ]

        # No uniqueness_constraint, no generic
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        assert _get_kinds_to_lock_on_object_mutation(kind="BuiltinIPPrefix", schema_branch=schema_branch) == []

    async def test_lock_other_branch(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema,
    ):
        other_branch = await create_branch(branch_name="other_branch", db=db)
        schema_branch = registry.schema.get_schema_branch(name=other_branch.name)

        person = await create_and_save(db=db, schema="TestPerson", name="John", branch=other_branch)
        assert get_lock_names_on_object_mutation(person, branch=other_branch, schema_branch=schema_branch) == []

    async def test_lock_groups_on_other_branches(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        register_core_models_schema,
    ):
        other_branch = await create_branch(branch_name="other_branch", db=db)
        schema_branch = registry.schema.get_schema_branch(name=other_branch.name)

        assert _should_kind_be_locked_on_any_branch(kind="CoreGraphQLQueryGroup", schema_branch=schema_branch) is True

    async def test_lock_names_only_attributes(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered,
    ):
        car_person_schema_unregistered = deepcopy(car_person_schema_unregistered)
        car_person_schema_unregistered.nodes[0].uniqueness_constraints = [
            ["name__value", "color__value", "owner__name"]
        ]
        registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)

        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person = await create_and_save(db=db, schema="TestPerson", name="John")
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", color="blue", owner=person)
        assert get_lock_names_on_object_mutation(car, branch=default_branch, schema_branch=schema_branch) == [
            "global.object.TestCar." + _hash("mercedes") + "." + _hash("blue")
        ]

    async def test_lock_names_optional_empty_attribute(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered,
    ):
        car_person_schema_unregistered = deepcopy(car_person_schema_unregistered)
        car_person_schema_unregistered.nodes[1].uniqueness_constraints = [["height__value"]]
        registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)

        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person = await create_and_save(db=db, schema="TestPerson", name="John")
        assert get_lock_names_on_object_mutation(person, branch=default_branch, schema_branch=schema_branch) == [
            "global.object.TestPerson." + _hash("") + "." + _hash("John")
        ]

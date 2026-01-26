from copy import deepcopy
from unittest.mock import patch

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants.infrahubkind import GRAPHQLQUERY, GRAPHQLQUERYGROUP
from infrahub.core.initialization import create_branch
from infrahub.core.node.lock_utils import (
    RELATIONSHIP_COUNT_LOCK_NAMESPACE,
    _get_kinds_to_lock_on_object_mutation,
    _hash,
    get_lock_names_on_object_mutation,
)
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp
from tests.node_creation import create_and_save


class TestGetKindsLock(TestInfrahubApp):
    async def test_get_kinds_lock(
        self,
        db: InfrahubDatabase,
        default_branch,
        register_core_models_schema,
        client,
    ) -> None:
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

    async def test_lock_core_graphql_query_groups(
        self,
        db: InfrahubDatabase,
        default_branch,
        register_core_models_schema,
        client,
    ) -> None:
        graphql_query = await client.create(
            kind=GRAPHQLQUERY,
            name="a_gql_query",
            query="""mutation MyMutation {
                        InfrahubAccountTokenDelete(data: {id: "%s"}) {
                            ok
                        }
                    }""",
        )
        await graphql_query.save()

        # Test create
        with patch("infrahub.core.node.create.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(kind=GRAPHQLQUERYGROUP, name="a_gql_group", query=graphql_query)
            await group.save()
            mock_infrahub_multi_lock.assert_called_once()
            call_kwargs = mock_infrahub_multi_lock.call_args.kwargs
            assert call_kwargs["lock_registry"] == lock.registry
            assert call_kwargs["metrics"] is False
            assert len(call_kwargs["locks"]) == 2
            assert call_kwargs["locks"][0] == "global.object.CoreGroup." + _hash("a_gql_group")
            # The second lock uses a temporary ID generated during node creation preview,
            # so we only verify the prefix pattern
            assert call_kwargs["locks"][1].startswith("relationship_count.coregraphqlquery__coregraphqlquerygroup.")

        # Test upsert the same node
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(kind=GRAPHQLQUERYGROUP, name="a_gql_group", query=graphql_query)
            await group.save(allow_upsert=True)

            mock_infrahub_multi_lock.assert_called_with(
                lock_registry=lock.registry,
                locks=[
                    "global.object.CoreGroup." + _hash("a_gql_group"),
                    "relationship_count.coregraphqlquery__coregraphqlquerygroup." + group.id,
                ],
                metrics=False,
            )

        # Test updating group name
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group.name = "new_group_name"
            await group.save()

            mock_infrahub_multi_lock.assert_called_once_with(
                lock_registry=lock.registry,
                locks=[
                    "global.object.CoreGroup." + _hash("new_group_name"),
                    "relationship_count.coregraphqlquery__coregraphqlquerygroup." + group.id,
                ],
                metrics=False,
            )

        # Test updating other field not present in uniqueness constraint
        # FIXME: not implemented yet
        # with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
        #     query = (
        #         """mutation {
        #         CoreGraphQLQueryGroupUpdate(
        #             data: {
        #                 id: "%s"
        #                 label: { value: "new_label"}
        #             }
        #         ){
        #             ok
        #         }
        #     }
        #     """
        #         % group.id
        #     )

        #     result = await client.execute_graphql(query=query)
        #     assert result["CoreGraphQLQueryGroupUpdate"]["ok"] is True

        #     mock_infrahub_multi_lock.assert_called_once_with(lock_registry=lock.registry, locks=[], metrics=False)

        # Test lock on another branch
        other_branch = await create_branch(branch_name="other_branch", db=db)
        with patch("infrahub.core.node.create.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(
                kind=GRAPHQLQUERYGROUP, name="one_more_group", query=graphql_query, branch=other_branch.name
            )
            await group.save()
            mock_infrahub_multi_lock.assert_called_once()
            call_kwargs = mock_infrahub_multi_lock.call_args.kwargs
            assert call_kwargs["lock_registry"] == lock.registry
            assert call_kwargs["metrics"] is False
            assert len(call_kwargs["locks"]) == 2
            assert call_kwargs["locks"][0] == "global.object.CoreGroup." + _hash("one_more_group")
            # The second lock uses a temporary ID generated during node creation preview,
            # so we only verify the prefix pattern
            assert call_kwargs["locks"][1].startswith("relationship_count.coregraphqlquery__coregraphqlquerygroup.")

    async def test_lock_other_branch(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema,
    ) -> None:
        other_branch = await create_branch(branch_name="other_branch", db=db)
        schema_branch = registry.schema.get_schema_branch(name=other_branch.name)

        person = await create_and_save(db=db, schema="TestPerson", name="John", branch=other_branch)
        assert get_lock_names_on_object_mutation(person, schema_branch=schema_branch) == [
            "global.object.TestPerson." + _hash("John")
        ]

    async def test_lock_names_only_attributes(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered,
    ) -> None:
        car_person_schema_unregistered = deepcopy(car_person_schema_unregistered)
        car_person_schema_unregistered.nodes[0].uniqueness_constraints = [
            ["name__value", "color__value", "owner__name"]
        ]
        registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)

        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person = await create_and_save(db=db, schema="TestPerson", name="John")
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", color="blue", owner=person)
        assert get_lock_names_on_object_mutation(car, schema_branch=schema_branch) == [
            "global.object.TestCar." + _hash("mercedes") + "." + _hash("blue"),
            "relationship_count.testcar__testperson." + car.id,
        ]

    async def test_lock_names_optional_empty_attribute(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered,
    ) -> None:
        car_person_schema_unregistered = deepcopy(car_person_schema_unregistered)
        car_person_schema_unregistered.nodes[1].uniqueness_constraints = [["height__value"]]
        registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)

        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        person = await create_and_save(db=db, schema="TestPerson", name="John")
        assert get_lock_names_on_object_mutation(person, schema_branch=schema_branch) == [
            "global.object.TestPerson." + _hash("") + "." + _hash("John")
        ]

    async def test_lock_names_peer_cardinality_one_relationship(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered: SchemaRoot,
    ) -> None:
        """Test that we add locks for relationships where the peer has cardinality one.

        Uses car_person_schema which already has Car->Person with cardinality one (owner).
        Person has a many relationship back via 'cars'.
        """
        schema = deepcopy(car_person_schema_unregistered)
        # Remove uniqueness constraints to focus on relationship locking
        schema.nodes[0].uniqueness_constraints = []
        schema.nodes[1].uniqueness_constraints = []
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # Create a person (the peer with cardinality one from Car's perspective)
        person = await create_and_save(db=db, schema="TestPerson", name="John")

        # Create a car linked to that person via the cardinality-one 'owner' relationship
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person)

        # The lock names should include the relationship_count lock for the person
        # because Car.owner has cardinality one
        lock_names = get_lock_names_on_object_mutation(car, schema_branch=schema_branch)

        expected_lock = f"{RELATIONSHIP_COUNT_LOCK_NAMESPACE}.testcar__testperson.{car.id}"
        assert expected_lock in lock_names

    async def test_lock_names_direct_cardinality_one_relationship(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered: SchemaRoot,
    ) -> None:
        """Test that we add locks for direct cardinality one relationships on the node side.

        Uses car_person_schema - Car has an optional cardinality one 'driver' relationship to Person.
        This tests the case where the node being created has an optional cardinality one relationship.
        """
        schema = deepcopy(car_person_schema_unregistered)
        # Remove uniqueness constraints to focus on relationship locking
        schema.nodes[0].uniqueness_constraints = []
        schema.nodes[1].uniqueness_constraints = []
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # Create persons - one as owner (required), one as driver (optional cardinality one)
        owner = await create_and_save(db=db, schema="TestPerson", name="John")
        driver = await create_and_save(db=db, schema="TestPerson", name="Jane")

        # Create a car with both owner and driver relationships
        # driver is an optional cardinality-one relationship (uses identifier "cars_driven__driver")
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=owner, driver=driver)

        # The lock names should include relationship_count locks for both cardinality one relationships
        lock_names = get_lock_names_on_object_mutation(car, schema_branch=schema_branch)

        # Lock for the owner relationship (Parent kind, cardinality one)
        owner_lock = f"{RELATIONSHIP_COUNT_LOCK_NAMESPACE}.testcar__testperson.{car.id}"
        # Lock for the driver relationship (cardinality one with identifier)
        driver_lock = f"{RELATIONSHIP_COUNT_LOCK_NAMESPACE}.cars_driven__driver.{car.id}"

        assert owner_lock in lock_names
        assert driver_lock in lock_names

    async def test_lock_names_max_count_relationship(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered: SchemaRoot,
    ) -> None:
        """Test that we add locks for relationships where the peer has max_count constraint.

        Modifies car_person_schema to add max_count on Person's cars relationship.
        """
        schema = deepcopy(car_person_schema_unregistered)
        # Remove uniqueness constraints to focus on relationship locking
        schema.nodes[0].uniqueness_constraints = []
        schema.nodes[1].uniqueness_constraints = []
        # Change owner from Parent to Generic (Parent has special constraints)
        schema.nodes[0].relationships[0].kind = "Generic"
        # Change Car's owner relationship to many with max_count
        schema.nodes[0].relationships[0].cardinality = "many"
        # Add max_count to Person's 'cars' relationship
        schema.nodes[1].relationships[0].max_count = 3
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # Create a person
        person = await create_and_save(db=db, schema="TestPerson", name="John")

        # Create a car linked to that person
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person)

        # The lock names should include the relationship_count lock for the person's ID
        # because Person.cars has max_count constraint
        lock_names = get_lock_names_on_object_mutation(car, schema_branch=schema_branch)

        expected_lock = f"{RELATIONSHIP_COUNT_LOCK_NAMESPACE}.testcar__testperson.{person.id}"
        assert expected_lock in lock_names

    async def test_lock_names_min_count_relationship(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered: SchemaRoot,
    ) -> None:
        """Test that we add locks for relationships where the peer has min_count constraint.

        Modifies car_person_schema to add min_count on Person's cars relationship.
        """
        schema = deepcopy(car_person_schema_unregistered)
        # Remove uniqueness constraints to focus on relationship locking
        schema.nodes[0].uniqueness_constraints = []
        schema.nodes[1].uniqueness_constraints = []
        # Change owner from Parent to Generic (Parent has special constraints)
        schema.nodes[0].relationships[0].kind = "Generic"
        # Change Car's owner relationship to many with min_count
        schema.nodes[0].relationships[0].cardinality = "many"
        # Add min_count to Person's 'cars' relationship
        schema.nodes[1].relationships[0].min_count = 1
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # Create a person
        person = await create_and_save(db=db, schema="TestPerson", name="John")

        # Create a car linked to that person
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person)

        # The lock names should include the relationship_count lock for the person's ID
        # because Person.cars has min_count constraint
        lock_names = get_lock_names_on_object_mutation(car, schema_branch=schema_branch)

        expected_lock = f"{RELATIONSHIP_COUNT_LOCK_NAMESPACE}.testcar__testperson.{person.id}"
        assert expected_lock in lock_names

    async def test_lock_names_direct_min_count_relationship(
        self,
        db: InfrahubDatabase,
        default_branch,
        client,
        car_person_schema_unregistered: SchemaRoot,
    ) -> None:
        """Test that we add locks for direct min_count relationships on the node side.

        Modifies car_person_schema to add min_count on Car's owner relationship.
        This tests the case where the node being created has a min_count constraint.
        """
        schema = deepcopy(car_person_schema_unregistered)
        # Remove uniqueness constraints to focus on relationship locking
        schema.nodes[0].uniqueness_constraints = []
        schema.nodes[1].uniqueness_constraints = []
        # Change Car's owner relationship to many with min_count
        schema.nodes[0].relationships[0].cardinality = "many"
        schema.nodes[0].relationships[0].min_count = 1
        schema.nodes[0].relationships[0].kind = "Generic"
        registry.schema.register_schema(schema=schema, branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        # Create persons
        person1 = await create_and_save(db=db, schema="TestPerson", name="John")
        person2 = await create_and_save(db=db, schema="TestPerson", name="Jane")

        # Create a car linked to persons
        car = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=[person1, person2])

        # The lock names should include the relationship_count lock for the car's node ID
        lock_names = get_lock_names_on_object_mutation(car, schema_branch=schema_branch)

        expected_lock = f"{RELATIONSHIP_COUNT_LOCK_NAMESPACE}.testcar__testperson.{car.id}"
        assert expected_lock in lock_names

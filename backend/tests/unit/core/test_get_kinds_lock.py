from copy import deepcopy
from unittest.mock import patch

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants.infrahubkind import GRAPHQLQUERY, GRAPHQLQUERYGROUP
from infrahub.core.initialization import create_branch
from infrahub.core.node.lock_utils import (
    _get_kinds_to_lock_on_object_mutation,
    _hash,
    get_lock_names_on_object_mutation,
)
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
            mock_infrahub_multi_lock.assert_called_once_with(
                lock_registry=lock.registry, locks=["global.object.CoreGroup." + _hash("a_gql_group")], metrics=False
            )

        # Test upsert the same node
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(kind=GRAPHQLQUERYGROUP, name="a_gql_group", query=graphql_query)
            await group.save(allow_upsert=True)

            mock_infrahub_multi_lock.assert_called_with(
                lock_registry=lock.registry, locks=["global.object.CoreGroup." + _hash("a_gql_group")], metrics=False
            )

        # Test updating group name
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group.name = "new_group_name"
            await group.save()

            mock_infrahub_multi_lock.assert_called_once_with(
                lock_registry=lock.registry, locks=["global.object.CoreGroup." + _hash("new_group_name")], metrics=False
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

        # Test lock onanother branch
        other_branch = await create_branch(branch_name="other_branch", db=db)
        with patch("infrahub.core.node.create.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(
                kind=GRAPHQLQUERYGROUP, name="one_more_group", query=graphql_query, branch=other_branch.name
            )
            await group.save()
            mock_infrahub_multi_lock.assert_called_once_with(
                lock_registry=lock.registry, locks=["global.object.CoreGroup." + _hash("one_more_group")], metrics=False
            )

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
            "global.object.TestCar." + _hash("mercedes") + "." + _hash("blue")
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

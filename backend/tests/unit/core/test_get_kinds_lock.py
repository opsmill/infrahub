from unittest.mock import patch

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants.infrahubkind import GRAPHQLQUERY, GRAPHQLQUERYGROUP
from infrahub.core.initialization import create_branch
from infrahub.core.node.lock_utils import _get_kinds_to_lock_on_object_mutation, _hash
from infrahub.database import InfrahubDatabase
from tests.helpers.test_app import TestInfrahubApp


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

    async def test_lock_core_graphql_query_groups(
        self,
        db: InfrahubDatabase,
        default_branch,
        register_core_models_schema,
        client,
    ):
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
                lock_registry=lock.registry, locks=["global.object.CoreGraphQLQueryGroup." + _hash("a_gql_group")]
            )

        # Test upsert the same node
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(kind=GRAPHQLQUERYGROUP, name="a_gql_group", query=graphql_query)
            await group.save(allow_upsert=True)

            mock_infrahub_multi_lock.assert_called_with(
                lock_registry=lock.registry, locks=["global.object.CoreGraphQLQueryGroup." + _hash("a_gql_group")]
            )

        # Test updating group name
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group.name = "new_group_name"
            await group.save()

            mock_infrahub_multi_lock.assert_called_once_with(
                lock_registry=lock.registry, locks=["global.object.CoreGraphQLQueryGroup." + _hash("new_group_name")]
            )

        # Test updating other field not present in uniqueness constraint
        with patch("infrahub.graphql.mutations.main.InfrahubMultiLock") as mock_infrahub_multi_lock:
            query = (
                """mutation {
                CoreGraphQLQueryGroupUpdate(
                    data: {
                        id: "%s"
                        label: { value: "new_label"}
                    }
                ){
                    ok
                }
            }
            """
                % group.id
            )

            result = await client.execute_graphql(query=query)
            assert result["CoreGraphQLQueryGroupUpdate"]["ok"] is True

            mock_infrahub_multi_lock.assert_not_called()

        # Test lock onanother branch
        other_branch = await create_branch(branch_name="other_branch", db=db)
        with patch("infrahub.core.node.create.InfrahubMultiLock") as mock_infrahub_multi_lock:
            group = await client.create(
                kind=GRAPHQLQUERYGROUP, name="one_more_group", query=graphql_query, branch=other_branch.name
            )
            await group.save()
            mock_infrahub_multi_lock.assert_called_once_with(
                lock_registry=lock.registry, locks=["global.object.CoreGraphQLQueryGroup." + _hash("one_more_group")]
            )

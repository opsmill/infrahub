from infrahub.core import registry
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.mutations.main import (
    _get_kind_lock_names_on_object_mutation,
    _get_kinds_to_lock_on_object_mutation,
)
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

    async def test_lock_graphql_query_group_other_branch(
        self,
        db: InfrahubDatabase,
        default_branch,
        register_core_models_schema,
        client,
    ):
        other_branch = await create_branch(branch_name="other_branch", db=db)
        schema_branch = registry.schema.get_schema_branch(name=other_branch.name)
        assert _get_kind_lock_names_on_object_mutation(
            kind="CoreGraphQLQueryGroup", branch=other_branch, schema_branch=schema_branch
        ) == ["global.object.CoreGroup"]

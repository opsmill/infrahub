from infrahub.core import registry
from infrahub.database import InfrahubDatabase
from infrahub.lock import get_kinds_to_lock_on_object_mutation
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
        core_password_credential_node = registry.schema.get("CorePasswordCredential")
        assert get_kinds_to_lock_on_object_mutation(core_password_credential_node) == ["CoreCredential"]

        # 3 generics but only GenericAccount has a uniqueness_constraint
        core_account_node = registry.schema.get("CoreAccount")
        assert get_kinds_to_lock_on_object_mutation(core_account_node) == ["CoreGenericAccount"]

        # No uniqueness_constraint, no generic
        core_account_node = registry.schema.get("BuiltinIPPrefix")
        assert get_kinds_to_lock_on_object_mutation(core_account_node) == []

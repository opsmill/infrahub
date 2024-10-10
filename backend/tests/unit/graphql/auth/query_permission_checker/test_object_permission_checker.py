from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import (
    AccountRole,
    GlobalPermissions,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
)
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.interface import CheckerResolution
from infrahub.graphql.auth.query_permission_checker.object_permission_checker import (
    AccountManagerPermissionChecker,
    ObjectPermissionChecker,
    PermissionManagerPermissionChecker,
    RepositoryManagerPermissionChecker,
)
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.unit.graphql.conftest import PermissionsHelper


QUERY_TAGS = """
query {
  BuiltinTag {
    edges {
      node {
        display_label
      }
    }
  }
}
"""

QUERY_REPOS = """
query {
  CoreRepository {
    edges {
      node {
        display_label
      }
    }
  }
}
"""

QUERY_GRAPHQL = """
query {
  CoreGraphQLQuery {
    edges {
      node {
        display_label
      }
    }
  }
}
"""

QUERY_GRAPHQL_AND_REPO = """
query {
  CoreGraphQLQuery {
    edges {
      node {
        display_label
        repository {
          node {
            display_label
          }
        }
      }
    }
  }
}
"""

MUTATION_ACCOUNT = """
mutation {
  CoreAccountCreate(data: {
    name: {value: "test"}
    password: {value: "test"}
  }) {
    ok
  }
}
"""

MUTATION_ACCOUNT_GROUP = """
mutation {
  CoreAccountGroupCreate(data: {
    name: {value: "test"}
  }) {
    ok
  }
}
"""

MUTATION_ACCOUNT_ROLE = """
mutation {
  CoreAccountRoleCreate(data: {
    name: {value: "test"}
  }) {
    ok
  }
}
"""

QUERY_ACCOUNT_PROFILE = """
query {
  AccountProfile {
    name {
      value
    }
  }
}
"""

MUTATION_GLOBAL_PERMISSION = """
mutation {
  CoreGlobalPermissionCreate(data: {
    name: {value: "Merge branch"}
    action: {value: "merge_branch"}
  }) {
    ok
    object {
      identifier {
        value
      }
    }
  }
}
"""

MUTATION_OBJECT_PERMISSION = """
mutation {
  CoreObjectPermissionCreate(data: {
    branch: {value: "*"}
    namespace: {value: "*"}
    name: {value: "*"}
  }) {
    ok
    object {
      identifier {
        value
      }
    }
  }
}
"""

QUERY_ACCOUNT_PERMISSIONS = """
query {
  InfrahubPermissions {
    global_permissions {
      edges {
        node {
          identifier
        }
      }
    }
    object_permissions {
      edges {
        node {
          identifier
        }
      }
    }
  }
}
"""

MUTATION_REPOSITORY = """
mutation {
  CoreRepositoryCreate(data: {
    name: {value: "Test"}
    location: {value: "/var/random"}
  }) {
    ok
  }
}
"""

MUTATION_READONLY_REPOSITORY = """
mutation {
  CoreReadOnlyRepositoryCreate(data: {
    name: {value: "Test"}
    location: {value: "/var/random"}
  }) {
    ok
  }
}
"""

MUTATION_GENERIC_REPOSITORY = """
mutation {
  CoreGenericRepositoryUpdate(data: {
    name: {value: "Test"}
    location: {value: "/var/random"}
  }) {
    ok
  }
}
"""


class TestObjectPermissions:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        default_branch: Branch,
        permissions_helper: PermissionsHelper,
        first_account: CoreAccount,
    ):
        registry.permission_backends = [LocalPermissionBackend()]
        permissions_helper._default_branch = default_branch

        permissions = []
        for object_permission in [
            ObjectPermission(
                id="",
                namespace="Builtin",
                name="*",
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOWED_DEFAULT.value,
            ),
            ObjectPermission(
                id="",
                namespace="Core",
                name="GraphQLQuery",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOWED_DEFAULT.value,
            ),
        ]:
            obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
            await obj.new(
                db=db,
                namespace=object_permission.namespace,
                name=object_permission.name,
                action=object_permission.action,
                decision=object_permission.decision,
            )
            await obj.save(db=db)
            permissions.append(obj)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admin", permissions=permissions)
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admin", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account

    async def test_first_account_tags(self, db: InfrahubDatabase, permissions_helper: PermissionsHelper) -> None:
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_TAGS, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        await perms.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            branch=permissions_helper.default_branch,
            query_parameters=gql_params,
        )

    async def test_first_account_repos(self, db: InfrahubDatabase, permissions_helper: PermissionsHelper) -> None:
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_REPOS, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        with pytest.raises(PermissionDeniedError, match=r":Repository:view:"):
            await perms.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                branch=permissions_helper.default_branch,
                query_parameters=gql_params,
            )

    async def test_first_account_graphql(self, db: InfrahubDatabase, permissions_helper: PermissionsHelper) -> None:
        """The user should have permissions to list GraphQLQueries."""
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_GRAPHQL, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        await perms.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            branch=permissions_helper.default_branch,
            query_parameters=gql_params,
        )

    async def test_first_account_graphql_and_repos(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ) -> None:
        """The user should have permissions to list GraphQLQueries but not repositories linked to them"""
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_GRAPHQL_AND_REPO, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        with pytest.raises(PermissionDeniedError, match=r"Repository:view:"):
            await perms.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                branch=permissions_helper.default_branch,
                query_parameters=gql_params,
            )


class TestAccountManagerPermissions:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        default_branch: Branch,
        permissions_helper: PermissionsHelper,
        first_account: CoreAccount,
        second_account: CoreAccount,
    ):
        registry.permission_backends = [LocalPermissionBackend()]
        permissions_helper._default_branch = default_branch

        permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await permission.new(
            db=db, name=GlobalPermissions.MANAGE_ACCOUNTS.value, action=GlobalPermissions.MANAGE_ACCOUNTS.value
        )
        await permission.save(db=db)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admin", permissions=[permission])
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admin", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account
        permissions_helper._second = second_account

    @pytest.mark.parametrize(
        "user",
        [
            AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN),
            AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE),
        ],
    )
    async def test_supports_manage_accounts_permission_accounts(
        self, user: AccountSession, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ):
        checker = AccountManagerPermissionChecker()
        is_supported = await checker.supports(db=db, account_session=user, branch=permissions_helper.default_branch)
        assert is_supported == user.authenticated

    @pytest.mark.parametrize("operation", [MUTATION_ACCOUNT, MUTATION_ACCOUNT_GROUP, MUTATION_ACCOUNT_ROLE])
    async def test_account_with_permission(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper, operation: str
    ):
        checker = AccountManagerPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=operation, schema=gql_params.schema, branch=permissions_helper.default_branch
        )

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            query_parameters=gql_params,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER

    @pytest.mark.parametrize(
        "operation,must_raise",
        [
            (MUTATION_ACCOUNT, True),
            (MUTATION_ACCOUNT_GROUP, True),
            (MUTATION_ACCOUNT_ROLE, True),
            (QUERY_TAGS, False),
            (QUERY_ACCOUNT_PROFILE, False),
        ],
    )
    async def test_account_without_permission(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper, operation: str, must_raise: bool
    ):
        checker = AccountManagerPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=operation, schema=gql_params.schema, branch=permissions_helper.default_branch
        )

        if not must_raise:
            resolution = await checker.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                query_parameters=gql_params,
                branch=permissions_helper.default_branch,
            )
            assert resolution == CheckerResolution.NEXT_CHECKER
        else:
            with pytest.raises(
                PermissionDeniedError, match=r"You do not have the permission to manage user accounts, groups or roles"
            ):
                await checker.check(
                    db=db,
                    account_session=session,
                    analyzed_query=analyzed_query,
                    query_parameters=gql_params,
                    branch=permissions_helper.default_branch,
                )


class TestPermissionManagerPermissions:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        default_branch: Branch,
        permissions_helper: PermissionsHelper,
        first_account: CoreAccount,
        second_account: CoreAccount,
    ):
        registry.permission_backends = [LocalPermissionBackend()]
        permissions_helper._default_branch = default_branch

        permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await permission.new(
            db=db, name=GlobalPermissions.MANAGE_PERMISSIONS.value, action=GlobalPermissions.MANAGE_PERMISSIONS.value
        )
        await permission.save(db=db)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admin", permissions=[permission])
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admin", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account
        permissions_helper._second = second_account

    @pytest.mark.parametrize(
        "user",
        [
            AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN),
            AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE),
        ],
    )
    async def test_supports_manage_accounts_permission_accounts(
        self, user: AccountSession, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ):
        checker = PermissionManagerPermissionChecker()
        is_supported = await checker.supports(db=db, account_session=user, branch=permissions_helper.default_branch)
        assert is_supported == user.authenticated

    @pytest.mark.parametrize(
        "operation", [MUTATION_GLOBAL_PERMISSION, MUTATION_OBJECT_PERMISSION, QUERY_ACCOUNT_PERMISSIONS]
    )
    async def test_account_with_permission(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper, operation: str
    ):
        checker = PermissionManagerPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=operation, schema=gql_params.schema, branch=permissions_helper.default_branch
        )

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            query_parameters=gql_params,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER

    @pytest.mark.parametrize(
        "operation,must_raise",
        [
            (MUTATION_GLOBAL_PERMISSION, True),
            (MUTATION_OBJECT_PERMISSION, True),
            (QUERY_TAGS, False),
            (QUERY_ACCOUNT_PERMISSIONS, False),
        ],
    )
    async def test_account_without_permission(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper, operation: str, must_raise: bool
    ):
        checker = PermissionManagerPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=operation, schema=gql_params.schema, branch=permissions_helper.default_branch
        )

        if not must_raise:
            resolution = await checker.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                query_parameters=gql_params,
                branch=permissions_helper.default_branch,
            )
            assert resolution == CheckerResolution.NEXT_CHECKER
        else:
            with pytest.raises(PermissionDeniedError, match=r"You do not have the permission to manage permissions"):
                await checker.check(
                    db=db,
                    account_session=session,
                    analyzed_query=analyzed_query,
                    query_parameters=gql_params,
                    branch=permissions_helper.default_branch,
                )


class TestRepositoryManagerPermissions:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        default_branch: Branch,
        permissions_helper: PermissionsHelper,
        first_account: CoreAccount,
        second_account: CoreAccount,
    ):
        registry.permission_backends = [LocalPermissionBackend()]
        permissions_helper._default_branch = default_branch

        permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await permission.new(
            db=db, name=GlobalPermissions.MANAGE_REPOSITORIES.value, action=GlobalPermissions.MANAGE_REPOSITORIES.value
        )
        await permission.save(db=db)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admin", permissions=[permission])
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admin", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account
        permissions_helper._second = second_account

    @pytest.mark.parametrize(
        "user",
        [
            AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN),
            AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE),
        ],
    )
    async def test_supports_manage_repositories_permission_accounts(
        self, user: AccountSession, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ):
        checker = AccountManagerPermissionChecker()
        is_supported = await checker.supports(db=db, account_session=user, branch=permissions_helper.default_branch)
        assert is_supported == user.authenticated

    @pytest.mark.parametrize(
        "operation", [MUTATION_REPOSITORY, MUTATION_READONLY_REPOSITORY, MUTATION_GENERIC_REPOSITORY]
    )
    async def test_account_with_permission(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper, operation: str
    ):
        checker = RepositoryManagerPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=operation, schema=gql_params.schema, branch=permissions_helper.default_branch
        )

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            query_parameters=gql_params,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER

    @pytest.mark.parametrize(
        "operation,must_raise",
        [
            (MUTATION_REPOSITORY, True),
            (MUTATION_READONLY_REPOSITORY, True),
            (MUTATION_GENERIC_REPOSITORY, True),
            (QUERY_TAGS, False),
        ],
    )
    async def test_account_without_permission(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper, operation: str, must_raise: bool
    ):
        checker = RepositoryManagerPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=operation, schema=gql_params.schema, branch=permissions_helper.default_branch
        )

        if not must_raise:
            resolution = await checker.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                query_parameters=gql_params,
                branch=permissions_helper.default_branch,
            )
            assert resolution == CheckerResolution.NEXT_CHECKER
        else:
            with pytest.raises(PermissionDeniedError, match=r"You do not have the permission to manage repositories"):
                await checker.check(
                    db=db,
                    account_session=session,
                    analyzed_query=analyzed_query,
                    query_parameters=gql_params,
                    branch=permissions_helper.default_branch,
                )

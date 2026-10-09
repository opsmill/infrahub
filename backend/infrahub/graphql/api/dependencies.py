from infrahub import config

from ..app import InfrahubGraphQLApp
from ..auth.query_permission_checker.anonymous_checker import AnonymousGraphQLPermissionChecker
from ..auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
from ..auth.query_permission_checker.default_branch_checker import DefaultBranchPermissionChecker
from ..auth.query_permission_checker.merge_operation_checker import MergeBranchPermissionChecker
from ..auth.query_permission_checker.object_permission_checker import (
    AccountManagerPermissionChecker,
    ObjectPermissionChecker,
    PermissionManagerPermissionChecker,
    RepositoryManagerPermissionChecker,
)
from ..auth.query_permission_checker.rebase_operation_checker import RebaseBranchPermissionChecker
from ..auth.query_permission_checker.super_admin_checker import SuperAdminPermissionChecker
from ..error_formatter import catalogue_error_formatter
from ..schema import QUERIES_REQUIRING_AUTHENTICATION


def get_anonymous_access_setting() -> bool:
    return config.SETTINGS.main.allow_anonymous_access


def build_graphql_query_permission_checker() -> GraphQLQueryPermissionChecker:
    return GraphQLQueryPermissionChecker(
        [
            AnonymousGraphQLPermissionChecker(
                anonymous_access_allowed_func=get_anonymous_access_setting,
                operations_requiring_authentication=QUERIES_REQUIRING_AUTHENTICATION,
            ),
            # This checker never raises, it either terminates the checker chains (user is super admin) or go to the next one
            SuperAdminPermissionChecker(),
            DefaultBranchPermissionChecker(),
            MergeBranchPermissionChecker(),
            RebaseBranchPermissionChecker(),
            AccountManagerPermissionChecker(),
            RepositoryManagerPermissionChecker(),
            PermissionManagerPermissionChecker(),
            ObjectPermissionChecker(),
        ]
    )


async def get_graphql_query_permission_checker() -> GraphQLQueryPermissionChecker:
    """Resolve the permission checker on the event loop, since FastAPI runs a sync dependency in a worker thread."""
    return build_graphql_query_permission_checker()


def build_graphql_app() -> InfrahubGraphQLApp:
    return InfrahubGraphQLApp(
        build_graphql_query_permission_checker(),
        error_formatter=catalogue_error_formatter,
    )

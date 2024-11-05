from typing import Any

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
)
from ..auth.query_permission_checker.read_only_checker import ReadOnlyGraphQLPermissionChecker
from ..auth.query_permission_checker.read_write_checker import ReadWriteGraphQLPermissionChecker
from ..auth.query_permission_checker.super_admin_checker import SuperAdminPermissionChecker


def get_anonymous_access_setting() -> bool:
    return config.SETTINGS.main.allow_anonymous_access


def build_graphql_query_permission_checker() -> GraphQLQueryPermissionChecker:
    return GraphQLQueryPermissionChecker(
        [
            AnonymousGraphQLPermissionChecker(get_anonymous_access_setting),
            # This checker never raises, it either terminates the checker chains (user is super admin) or go to the next one
            SuperAdminPermissionChecker(),
            DefaultBranchPermissionChecker(),
            MergeBranchPermissionChecker(),
            AccountManagerPermissionChecker(),
            PermissionManagerPermissionChecker(),
            ObjectPermissionChecker(),
            ReadWriteGraphQLPermissionChecker(),  # Deprecated, will be replace by either a global permission or object permissions
            ReadOnlyGraphQLPermissionChecker(),  # Deprecated, will be replace by either a global permission or object permissions
        ]
    )


def build_graphql_app(**kwargs: Any) -> InfrahubGraphQLApp:
    return InfrahubGraphQLApp(build_graphql_query_permission_checker(), **kwargs)

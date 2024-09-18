from typing import Any

from infrahub import config

from ..app import InfrahubGraphQLApp
from ..auth.query_permission_checker.anonymous_checker import AnonymousGraphQLPermissionChecker
from ..auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
from ..auth.query_permission_checker.default_branch_checker import DefaultBranchPermissionChecker
from ..auth.query_permission_checker.default_checker import DefaultGraphQLPermissionChecker
from ..auth.query_permission_checker.object_permission_checker import ObjectPermissionChecker
from ..auth.query_permission_checker.read_only_checker import ReadOnlyGraphQLPermissionChecker
from ..auth.query_permission_checker.read_write_checker import ReadWriteGraphQLPermissionChecker


def get_anonymous_access_setting() -> bool:
    return config.SETTINGS.main.allow_anonymous_access


def build_graphql_query_permission_checker() -> GraphQLQueryPermissionChecker:
    return GraphQLQueryPermissionChecker(
        [
            DefaultBranchPermissionChecker(),
            ObjectPermissionChecker(),
            ReadWriteGraphQLPermissionChecker(),  # Deprecated, will be replace by either a global permission or object permissions
            ReadOnlyGraphQLPermissionChecker(),  # Deprecated, will be replace by either a global permission or object permissions
            AnonymousGraphQLPermissionChecker(get_anonymous_access_setting),
            DefaultGraphQLPermissionChecker(),
        ]
    )


def build_graphql_app(**kwargs: Any) -> InfrahubGraphQLApp:
    return InfrahubGraphQLApp(build_graphql_query_permission_checker(), **kwargs)

from typing import Any

import infrahub.config as config

from ..app import InfrahubGraphQLApp
from ..auth.query_permission_checker.anonymous_checker import AnonymousGraphQLPermissionChecker
from ..auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
from ..auth.query_permission_checker.default_checker import DefaultGraphQLPermissionChecker
from ..auth.query_permission_checker.read_only_checker import ReadOnlyGraphQLPermissionChecker
from ..auth.query_permission_checker.read_write_checker import ReadWriteGraphQLPermissionChecker
from .graphiql import make_graphiql_handler


def get_anonymous_access_setting() -> bool:
    return config.SETTINGS.main.allow_anonymous_access


def build_graphql_query_permission_checker() -> GraphQLQueryPermissionChecker:
    return GraphQLQueryPermissionChecker(
        [
            ReadWriteGraphQLPermissionChecker(),
            ReadOnlyGraphQLPermissionChecker(),
            AnonymousGraphQLPermissionChecker(get_anonymous_access_setting),
            DefaultGraphQLPermissionChecker(),
        ]
    )


def build_graphql_app(**kwargs: Any) -> InfrahubGraphQLApp:
    if "on_get" not in kwargs:
        kwargs["on_get"] = make_graphiql_handler()
    return InfrahubGraphQLApp(build_graphql_query_permission_checker(), **kwargs)

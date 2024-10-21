from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from starlette.background import BackgroundTasks

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError

from .manager import GraphQLSchemaManager

if TYPE_CHECKING:
    from graphql import GraphQLSchema
    from starlette.requests import HTTPConnection

    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


@dataclass
class GraphqlParams:
    schema: GraphQLSchema
    context: GraphqlContext


@dataclass
class GraphqlContext:
    db: InfrahubDatabase
    branch: Branch
    types: dict
    at: Optional[Timestamp] = None
    related_node_ids: Optional[set] = None
    service: Optional[InfrahubServices] = None
    account_session: Optional[AccountSession] = None
    background: Optional[BackgroundTasks] = None
    request: Optional[HTTPConnection] = None

    @property
    def active_account_session(self) -> AccountSession:
        """Return an account session or raise an error

        Eventualy this property should be removed, that can be done after self.account_session is no longer optional
        """
        if self.account_session:
            return self.account_session
        raise InitializationError("GraphQLContext doesn't contain an account_session")


def prepare_graphql_params(
    db: InfrahubDatabase,
    branch: Branch | str,
    at: Timestamp | str | None = None,
    account_session: AccountSession | None = None,
    request: HTTPConnection | None = None,
    service: InfrahubServices | None = None,
    include_query: bool = True,
    include_mutation: bool = True,
    include_subscription: bool = True,
    include_types: bool = True,
) -> GraphqlParams:
    branch = registry.get_branch_from_registry(branch=branch)
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    gqlm = GraphQLSchemaManager.get_manager_for_branch(branch=branch, schema_branch=schema_branch)
    gql_schema = gqlm.get_graphql_schema(
        include_query=include_query,
        include_mutation=include_mutation,
        include_subscription=include_subscription,
        include_types=include_types,
    )

    if request and not service:
        service = request.app.state.service

    return GraphqlParams(
        schema=gql_schema,
        context=GraphqlContext(
            db=db,
            branch=branch,
            at=Timestamp(at),
            types=gqlm.get_graphql_types(),
            related_node_ids=set(),
            background=BackgroundTasks(),
            request=request,
            service=service,
            account_session=account_session,
        ),
    )

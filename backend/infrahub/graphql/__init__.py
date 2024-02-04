from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union

from starlette.background import BackgroundTasks

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp

from .manager import GraphQLSchemaManager

if TYPE_CHECKING:
    from graphql import GraphQLSchema
    from starlette.requests import HTTPConnection

    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus.rpc import InfrahubRpcClient


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
    _rpc_client: Optional[InfrahubRpcClient] = None
    _account_session: Optional[AccountSession] = None
    background: Optional[BackgroundTasks] = None
    request: Optional[HTTPConnection] = None

    @property
    def account_session(self) -> AccountSession:
        if self._account_session:
            return self._account_session
        raise ValueError("account_session isn't available on GraphqlContext")

    @property
    def rpc_client(self) -> InfrahubRpcClient:
        if self._rpc_client:
            return self._rpc_client
        raise ValueError("rpc_client isn't available on GraphqlContext")


def prepare_graphql_params(
    db: InfrahubDatabase,  # pylint: disable=unused-argument
    branch: Union[Branch, str],
    at: Optional[Union[Timestamp, str]] = None,
    account_session: Optional[AccountSession] = None,
    request: Optional[HTTPConnection] = None,
    rpc_client: Optional[InfrahubRpcClient] = None,
    include_query: bool = True,
    include_mutation: bool = True,
    include_subscription: bool = True,
    include_types: bool = True,
) -> GraphqlParams:
    branch = registry.get_branch_from_registry(branch=branch)
    schema = registry.schema.get_schema_branch(name=branch.name)

    gqlm = GraphQLSchemaManager(schema=schema)
    gql_schema = gqlm.generate(
        include_query=include_query,
        include_mutation=include_mutation,
        include_subscription=include_subscription,
        include_types=include_types,
    )

    if request and not rpc_client:
        rpc_client = request.app.state.rpc_client

    return GraphqlParams(
        schema=gql_schema,
        context=GraphqlContext(
            db=db,
            branch=branch,
            at=Timestamp(at),
            types=gqlm._graphql_types,
            related_node_ids=set(),
            background=BackgroundTasks(),
            request=request,
            _rpc_client=rpc_client,
            _account_session=account_session,
        ),
    )


def generate_graphql_schema(
    db: InfrahubDatabase,  # pylint: disable=unused-argument
    branch: Union[Branch, str],
    include_query: bool = True,
    include_mutation: bool = True,
    include_subscription: bool = True,
    include_types: bool = True,
) -> GraphQLSchema:
    branch = registry.get_branch_from_registry(branch)
    schema = registry.schema.get_schema_branch(name=branch.name)
    return GraphQLSchemaManager(schema=schema).generate(
        include_query=include_query,
        include_mutation=include_mutation,
        include_subscription=include_subscription,
        include_types=include_types,
    )

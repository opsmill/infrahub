from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.background import BackgroundTasks

from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import InitializationError
from infrahub.graphql.resolvers.many_relationship import ManyRelationshipResolver
from infrahub.graphql.resolvers.single_relationship import SingleRelationshipResolver
from infrahub.permissions import PermissionManager

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
    single_relationship_resolver: SingleRelationshipResolver
    many_relationship_resolver: ManyRelationshipResolver
    service: InfrahubServices | None = None
    at: Timestamp | None = None
    related_node_ids: set | None = None
    account_session: AccountSession | None = None
    permissions: PermissionManager | None = None
    background: BackgroundTasks | None = None
    request: HTTPConnection | None = None

    @property
    def active_account_session(self) -> AccountSession:
        """Return an account session or raise an error

        Eventualy this property should be removed, that can be done after self.account_session is no longer optional
        """
        if self.account_session:
            return self.account_session
        raise InitializationError("GraphQLContext doesn't contain an account_session")

    @property
    def active_permissions(self) -> PermissionManager:
        """Return a permission manager or raise an error

        This property should be removed, once self.account_session is no longer optional which will imply self.permissions will no longer be optional
        as well.
        """
        if self.permissions:
            return self.permissions
        raise InitializationError("GraphQLContext doesn't contain permissions")

    @property
    def active_service(self) -> InfrahubServices:
        if self.service:
            return self.service
        raise InitializationError("GraphQLContext doesn't contain a service")

    def get_context(self) -> InfrahubContext:
        return InfrahubContext.init(branch=self.branch, account=self.active_account_session)


async def prepare_graphql_params(
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

    permissions: PermissionManager | None = None
    if account_session:
        permissions = PermissionManager(account_session=account_session)
        await permissions.load_permissions(db=db, branch=branch)

    return GraphqlParams(
        schema=gql_schema,
        context=GraphqlContext(
            db=db,
            branch=branch,
            single_relationship_resolver=SingleRelationshipResolver(),
            many_relationship_resolver=ManyRelationshipResolver(),
            at=Timestamp(at),
            types=gqlm.get_graphql_types(),
            related_node_ids=set(),
            background=BackgroundTasks(),
            request=request,
            service=service,
            account_session=account_session,
            permissions=permissions,
        ),
    )

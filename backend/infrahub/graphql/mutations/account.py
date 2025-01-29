from typing import TYPE_CHECKING, Any

from graphene import Boolean, Field, InputField, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from infrahub_sdk.utils import extract_fields
from infrahub_sdk.uuidt import UUIDT
from typing_extensions import Self

from infrahub.auth import AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount, CoreNode, InternalAccountToken
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import NodeNotFoundError, PermissionDeniedError

from ..models import OrderModel
from ..types import InfrahubObjectType

if TYPE_CHECKING:
    from ..initialization import GraphqlContext


class InfrahubAccountTokenCreateInput(InputObjectType):
    name = InputField(String(required=False), description="The name of the token")
    expiration = InputField(String(required=False), description="Timestamp when the token expires")


class InfrahubAccountTokenDeleteInput(InputObjectType):
    id = InputField(String(required=True), description="The id of the token to delete")


class InfrahubAccountUpdateSelfInput(InputObjectType):
    password = InputField(String(required=False), description="Password to use instead of the current one")
    description = InputField(String(required=False), description="Description to use instead of the current one")


class ValueType(InfrahubObjectType):
    value = String(required=True)


class InfrahubAccountTokenType(InfrahubObjectType):
    id = String(required=True)
    token = Field(ValueType)


class AccountMixin:
    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: dict[str, Any],
    ) -> Self:
        graphql_context: GraphqlContext = info.context

        if not graphql_context.account_session:
            raise ValueError("An account_session is mandatory to execute this mutation")

        if graphql_context.account_session.auth_type != AuthType.JWT:
            raise PermissionDeniedError("This operation requires authentication with a JWT token")

        results = await NodeManager.query(
            schema=CoreAccount, filters={"ids": [graphql_context.account_session.account_id]}, db=graphql_context.db
        )
        if not results:
            raise NodeNotFoundError(
                node_type=InfrahubKind.ACCOUNT, identifier=graphql_context.account_session.account_id
            )

        account = results[0]

        mutation_map = {
            "InfrahubAccountTokenCreate": cls.create_token,
            "InfrahubAccountTokenDelete": cls.delete_token,
            "InfrahubAccountSelfUpdate": cls.update_self,
        }
        response = await mutation_map[cls.__name__](db=graphql_context.db, account=account, data=data, info=info)

        # Reset the time of the query to guarantee that all resolvers executed after this point will account for the changes
        graphql_context.at = Timestamp()

        return response

    @classmethod
    @retry_db_transaction(name="account_token_create")
    async def create_token(
        cls, db: InfrahubDatabase, account: CoreNode, data: dict[str, Any], info: GraphQLResolveInfo
    ) -> Self:
        obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
        token = str(UUIDT())
        await obj.new(
            db=db,
            account=account,
            token=token,
            name=data.get("name"),
            expiration=data.get("expiration"),
        )

        async with db.start_transaction() as dbt:
            await obj.save(db=dbt)

        fields = await extract_fields(info.field_nodes[0].selection_set)
        return cls(object=await obj.to_graphql(db=db, fields=fields.get("object", {})), ok=True)  # type: ignore[call-arg]

    @classmethod
    @retry_db_transaction(name="account_token_delete")
    async def delete_token(
        cls,
        db: InfrahubDatabase,
        account: CoreNode,
        data: dict[str, Any],
        info: GraphQLResolveInfo,  # noqa: ARG003
    ) -> Self:
        token_id = str(data.get("id"))

        results = await NodeManager.query(
            schema=InternalAccountToken,
            filters={"account_ids": [account.id], "ids": [token_id]},
            db=db,
            order=OrderModel(disable=True),
        )

        if not results:
            raise NodeNotFoundError(node_type="AccountToken", identifier=token_id)

        async with db.start_transaction() as dbt:
            await results[0].delete(db=dbt)

        return cls(ok=True)  # type: ignore[call-arg]

    @classmethod
    @retry_db_transaction(name="account_update_self")
    async def update_self(
        cls,
        db: InfrahubDatabase,
        account: CoreNode,
        data: dict[str, Any],
        info: GraphQLResolveInfo,  # noqa: ARG003
    ) -> Self:
        for field in ("password", "description"):
            if value := data.get(field):
                getattr(account, field).value = value

        async with db.start_transaction() as dbt:
            await account.save(db=dbt)

        return cls(ok=True)  # type: ignore[call-arg]


class InfrahubAccountTokenCreate(AccountMixin, Mutation):
    class Arguments:
        data = InfrahubAccountTokenCreateInput(required=True)

    ok = Boolean()
    object = Field(InfrahubAccountTokenType)


class InfrahubAccountTokenDelete(AccountMixin, Mutation):
    class Arguments:
        data = InfrahubAccountTokenDeleteInput(required=True)

    ok = Boolean()


class InfrahubAccountSelfUpdate(AccountMixin, Mutation):
    class Arguments:
        data = InfrahubAccountUpdateSelfInput(required=True)

    ok = Boolean()

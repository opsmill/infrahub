from typing import TYPE_CHECKING, Any, Dict

from graphene import Boolean, Field, InputField, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from infrahub_sdk import UUIDT
from infrahub_sdk.utils import extract_fields
from typing_extensions import Self

from infrahub.auth import AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFound, PermissionDeniedError

from ..types import InfrahubObjectType

if TYPE_CHECKING:
    from .. import GraphqlContext


# pylint: disable=unused-argument


class CoreAccountTokenCreateInput(InputObjectType):
    name = InputField(String(required=False), description="The name of the token")
    expiration = InputField(String(required=False), description="Timestamp when the token expires")


class CoreAccountUpdateSelfInput(InputObjectType):
    password = InputField(String(required=False), description="The new password")
    description = InputField(String(required=False), description="The new description")


class ValueType(InfrahubObjectType):
    value = String(required=True)


class CoreAccountTokenType(InfrahubObjectType):
    token = Field(ValueType)


class AccountMixin:
    @classmethod
    async def mutate(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: Dict[str, Any],
    ) -> Self:
        context: GraphqlContext = info.context

        if not context.account_session:
            raise ValueError("An account_session is mandatory to execute this mutation")

        if context.account_session.auth_type != AuthType.JWT:
            raise PermissionDeniedError("This operation requires authentication with a JWT token")

        results = await NodeManager.query(
            schema=InfrahubKind.ACCOUNT, filters={"ids": [context.account_session.account_id]}, db=context.db
        )
        if not results:
            raise NodeNotFound(node_type=InfrahubKind.ACCOUNT, identifier=context.account_session.account_id)

        account = results[0]

        mutation_map = {"CoreAccountTokenCreate": cls.create_token, "CoreAccountSelfUpdate": cls.update_self}
        response = await mutation_map[cls.__name__](db=context.db, account=account, data=data, info=info)

        # Reset the time of the query to guarantee that all resolvers executed after this point will account for the changes
        context.at = Timestamp()

        return response

    @classmethod
    async def create_token(
        cls, db: InfrahubDatabase, account: Node, data: Dict[str, Any], info: GraphQLResolveInfo
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
    async def update_self(
        cls, db: InfrahubDatabase, account: Node, data: Dict[str, Any], info: GraphQLResolveInfo
    ) -> Self:
        for field in ("password", "description"):
            if value := data.get(field):
                getattr(account, field).value = value

        async with db.start_transaction() as dbt:
            await account.save(db=dbt)

        return cls(ok=True)  # type: ignore[call-arg]


class CoreAccountTokenCreate(AccountMixin, Mutation):
    class Arguments:
        data = CoreAccountTokenCreateInput(required=True)

    ok = Boolean()
    object = Field(CoreAccountTokenType)


class CoreAccountSelfUpdate(AccountMixin, Mutation):
    class Arguments:
        data = CoreAccountUpdateSelfInput(required=True)

    ok = Boolean()

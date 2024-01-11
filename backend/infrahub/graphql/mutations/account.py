from typing import TYPE_CHECKING, Dict

from graphene import Boolean, Field, InputField, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from infrahub_sdk import UUIDT

from infrahub.auth import AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFound, PermissionDeniedError

from ..types import InfrahubObjectType
from ..utils import extract_fields

if TYPE_CHECKING:
    from infrahub.auth import AccountSession


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
        data,
    ):
        db: InfrahubDatabase = info.context.get("infrahub_database")
        account_session: AccountSession = info.context.get("account_session")

        if account_session.auth_type != AuthType.JWT:
            raise PermissionDeniedError("This operation requires authentication with a JWT token")

        results = await NodeManager.query(
            schema=InfrahubKind.ACCOUNT, filters={"ids": [account_session.account_id]}, db=db
        )
        if not results:
            raise NodeNotFound(
                branch_name="main", node_type=InfrahubKind.ACCOUNT, identifier=account_session.account_id
            )

        account = results[0]

        mutation_map = {"CoreAccountTokenCreate": cls.create_token, "CoreAccountSelfUpdate": cls.update_self}
        return await mutation_map[cls.__name__](db=db, account=account, data=data, info=info)

    @classmethod
    async def create_token(cls, db: InfrahubDatabase, account: Node, data: Dict, info: GraphQLResolveInfo):
        obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
        token = str(UUIDT())
        await obj.new(
            db=db,
            account=account,
            token=token,
            name=data.get("name"),
            expiration=data.get("expiration"),
        )

        async with db.start_transaction() as db:
            await obj.save(db=db)

        fields = await extract_fields(info.field_nodes[0].selection_set)
        return cls(object=await obj.to_graphql(db=db, fields=fields.get("object", {})), ok=True)

    @classmethod
    async def update_self(cls, db: InfrahubDatabase, account: Node, data: Dict, info: GraphQLResolveInfo):
        for field in ("password", "description"):
            if value := data.get(field):
                getattr(account, field).value = value

        async with db.start_transaction() as db:
            await account.save(db=db)

        return cls(ok=True)


class CoreAccountTokenCreate(AccountMixin, Mutation):
    class Arguments:
        data = CoreAccountTokenCreateInput(required=True)

    ok = Boolean()
    object = Field(CoreAccountTokenType)


class CoreAccountSelfUpdate(AccountMixin, Mutation):
    class Arguments:
        data = CoreAccountUpdateSelfInput(required=True)

    ok = Boolean()

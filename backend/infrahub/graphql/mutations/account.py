from typing import TYPE_CHECKING, Dict
from uuid import uuid4

from graphene import Boolean, Field, InputField, InputObjectType, Mutation, String
from graphql import GraphQLResolveInfo
from neo4j import AsyncSession

from infrahub.auth import AuthType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.exceptions import NodeNotFound, PermissionDeniedError

from ..types import InfrahubObjectType
from ..utils import extract_fields

if TYPE_CHECKING:
    from infrahub.auth import AccountSession

# pylint: disable=unused-argument


class CoreAccountTokenCreateInput(InputObjectType):
    name = InputField(String(required=False), description="The name of the token")
    expiration = InputField(String(required=False), description="Timestamp when the token expires")


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
        session: AsyncSession = info.context.get("infrahub_session")
        account_session: AccountSession = info.context.get("account_session")

        if account_session.auth_type != AuthType.JWT:
            raise PermissionDeniedError("This operation requires authentication with a JWT token")

        results = await NodeManager.query(
            schema="CoreAccount", filters={"ids": [account_session.account_id]}, session=session
        )
        if not results:
            raise NodeNotFound(branch_name="main", node_type="CoreAccount", identifier=account_session.account_id)

        account = results[0]

        mutation_map = {"CoreAccountTokenCreate": cls.create_token}
        return await mutation_map[cls.__name__](session=session, account=account, data=data, info=info)

    @classmethod
    async def create_token(cls, session: AsyncSession, account: Node, data: Dict, info: GraphQLResolveInfo):
        obj = await Node.init(session=session, schema="InternalAccountToken")
        token = str(uuid4())
        await obj.new(
            session=session,
            account=account,
            token=token,
            name=data.get("name"),
            expiration=data.get("expiration"),
        )
        await obj.save(session=session)

        fields = await extract_fields(info.field_nodes[0].selection_set)
        return cls(object=await obj.to_graphql(session=session, fields=fields.get("object", {})), ok=True)


class CoreAccountTokenCreate(AccountMixin, Mutation):
    class Arguments:
        data = CoreAccountTokenCreateInput(required=True)

    ok = Boolean()
    object = Field(CoreAccountTokenType)

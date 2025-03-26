from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import ObjectType
from graphene.types.objecttype import ObjectTypeOptions

from infrahub import config

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class InfrahubObjectTypeOptions(ObjectTypeOptions):
    model = None


class InfrahubObjectType(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(cls, model=None, interfaces=(), _meta=None, **options) -> None:
        if not _meta:
            _meta = InfrahubObjectTypeOptions(cls)

        _meta.model = model

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)

    @classmethod
    async def get_list(cls, fields: dict[str, Any], graphql_context: GraphqlContext, **kwargs) -> list[dict[str, Any]]:
        async with graphql_context.db.session(database=config.SETTINGS.database.database_name) as db:
            filters = {key: value for key, value in kwargs.items() if "__" in key and value}

            if filters:
                objs = await cls._meta.model.get_list(
                    filters=filters,
                    at=graphql_context.at,
                    branch=graphql_context.branch,
                    account=graphql_context.account_session,
                    include_source=True,
                    db=db,
                )
            else:
                objs = await cls._meta.model.get_list(
                    at=graphql_context.at,
                    branch=graphql_context.branch,
                    account=graphql_context.account_session,
                    include_source=True,
                    db=db,
                )

            if not objs:
                return []

            return [obj.to_graphql(fields=fields) for obj in objs]

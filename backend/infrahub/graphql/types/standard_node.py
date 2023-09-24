from __future__ import annotations

from graphene import ObjectType
from graphene.types.objecttype import ObjectTypeOptions

import infrahub.config as config


class InfrahubObjectTypeOptions(ObjectTypeOptions):
    model = None


class InfrahubObjectType(ObjectType):
    @classmethod
    def __init_subclass_with_meta__(  # pylint: disable=arguments-differ
        cls,
        model=None,
        interfaces=(),
        _meta=None,
        **options,
    ):
        if not _meta:
            _meta = InfrahubObjectTypeOptions(cls)

        _meta.model = model

        super().__init_subclass_with_meta__(_meta=_meta, interfaces=interfaces, **options)

    @classmethod
    async def get_list(cls, fields, context, **kwargs):
        at = context.get("infrahub_at")
        branch = context.get("infrahub_branch")
        account = context.get("infrahub_account", None)
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            filters = {key: value for key, value in kwargs.items() if "__" in key and value}

            if filters:
                objs = await cls._meta.model.get_list(
                    filters=filters, at=at, branch=branch, account=account, include_source=True, db=db
                )
            else:
                objs = await cls._meta.model.get_list(at=at, branch=branch, account=account, include_source=True, db=db)

            if not objs:
                return []

            return [obj.to_graphql(fields=fields) for obj in objs]

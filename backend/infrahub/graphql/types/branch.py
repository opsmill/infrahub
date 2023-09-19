from __future__ import annotations

from graphene import Boolean, String

import infrahub.config as config
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME

from .standard_node import InfrahubObjectType


class BranchType(InfrahubObjectType):
    id = String(required=True)
    name = String(required=True)
    description = String(required=False)
    origin_branch = String(required=False)
    branched_from = String(required=False)
    created_at = String(required=False)
    is_data_only = Boolean(required=False)
    is_default = Boolean(required=False)

    class Meta:
        description = "Branch"
        name = "Branch"
        model = Branch

    @classmethod
    async def get_list(cls, fields: dict, context: dict, *args, **kwargs):  # pylint: disable=unused-argument
        db = context.get("infrahub_database")

        async with db.session(database=config.SETTINGS.database.database) as session:
            context["infrahub_session"] = session

            objs = await Branch.get_list(session=session, **kwargs)

            if not objs:
                return []

            return [obj.to_graphql(fields=fields) for obj in objs if obj.name != GLOBAL_BRANCH_NAME]

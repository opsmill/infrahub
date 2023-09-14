from __future__ import annotations

from graphene import Boolean, Field, List, ObjectType, String
from graphene.types.generic import GenericScalar

import infrahub.config as config
from infrahub.core import get_branch
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


class BranchDiffPropertyValueType(ObjectType):
    new = GenericScalar()
    previous = GenericScalar()


class BranchDiffPropertyType(ObjectType):
    branch = String()
    type = String()
    changed_at = String()
    action = String()
    value = Field(BranchDiffPropertyValueType)


class BranchDiffAttributeType(ObjectType):
    name = String()
    id = String()
    changed_at = String()
    action = String()
    properties = List(BranchDiffPropertyType)


class BranchDiffNodeType(ObjectType):
    branch = String()
    kind = String()
    id = String()
    changed_at = String()
    action = String()
    attributes = List(BranchDiffAttributeType)


class BranchDiffRelationshipEdgeNodeType(ObjectType):
    id = String()
    kind = String()


class BranchDiffRelationshipType(ObjectType):
    branch = String()
    id = String()
    name = String()
    nodes = List(BranchDiffRelationshipEdgeNodeType)
    properties = List(BranchDiffPropertyType)
    changed_at = String()
    action = String()


class BranchDiffFileType(ObjectType):
    branch = String()
    repository = String()
    location = String()
    action = String()


class BranchDiffType(ObjectType):
    nodes = List(BranchDiffNodeType)
    files = List(BranchDiffFileType)
    relationships = List(BranchDiffRelationshipType)

    @classmethod
    async def get_diff(
        cls, branch, diff_from: str, diff_to: str, branch_only: bool, fields: dict, context: dict, *args, **kwargs
    ):  # pylint: disable=unused-argument
        context.get("infrahub_at")
        session = context.get("infrahub_session")
        rpc_client = context.get("infrahub_rpc_client")

        branch = await get_branch(branch=branch, session=session)

        diff = await branch.diff(session=session, diff_from=diff_from, diff_to=diff_to, branch_only=branch_only)

        response = {
            "nodes": [],
            "files": [],
            "relationships": [],
        }
        if "nodes" in fields:
            nodes = await diff.get_nodes(session=session)
            for items in nodes.values():
                for item in items.values():
                    response["nodes"].append(item.to_graphql())

        if "relationships" in fields:
            rels = await diff.get_relationships(session=session)

            for items in rels.values():
                for item in items.values():
                    for sub_item in item.values():
                        response["relationships"].append(sub_item.to_graphql())

        if "files" in fields:
            files = await diff.get_files(rpc_client=rpc_client, session=session)
            for items in files.values():
                for item in items:
                    response["files"].append(item.to_graphql())

        return response

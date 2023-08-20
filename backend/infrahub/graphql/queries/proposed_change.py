from typing import TYPE_CHECKING

from graphene import Boolean, Field, List, ObjectType, String
from graphql import GraphQLResolveInfo

from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.exceptions import NodeNotFound
from infrahub.graphql.utils import extract_fields

if TYPE_CHECKING:
    from neo4j import AsyncSession


class ProposedChangeChecks(ObjectType):
    id = String()
    success = Boolean()
    data_conflicts = List(String)
    last_data_check = String()

    @classmethod
    async def resolve(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        id: str,  # pylint: disable=redefined-builtin
        **kwargs,
    ):  # pylint: disable=unused-argument
        fields = await extract_fields(info.field_nodes[0].selection_set)
        return await ProposedChangeChecks.get_checks(
            fields=fields,
            context=info.context,
            id=id,
        )

    @classmethod
    async def get_checks(
        cls, id: str, fields: dict, context: dict, *args, **kwargs
    ):  # pylint: disable=unused-argument, redefined-builtin
        context.get("infrahub_at")
        session: AsyncSession = context.get("infrahub_session")
        # rpc_client = context.get("infrahub_rpc_client")

        proposed_change = await NodeManager.get_one(id=id, session=session)
        if not proposed_change:
            raise NodeNotFound(
                branch_name="-global-",
                node_type="CoreProposedChange",
                identifier=id,
                message="The requested proposed change wasn't found",
            )

        response = await proposed_change.to_graphql(session=session)

        data_validator = registry.get_schema(name="InternalDataIntegrityValidator")

        checks = await NodeManager.query(data_validator, filters={"proposed_change__ids": [id]}, session=session)
        sorted_checks = sorted(checks, key=lambda x: x._updated_at, reverse=True)
        last_check = sorted_checks[0]
        response = {
            "id": id,
            "success": last_check.status.value == "passed",
            "data_conflicts": last_check.conflict_paths.value,
            "last_data_check": last_check._updated_at.to_string(),
        }
        return response


ProposedChangeCheckField = Field(
    ProposedChangeChecks,
    resolver=ProposedChangeChecks.resolve,
    id=String(required=True, description="The ID of the ProposedChange"),
)

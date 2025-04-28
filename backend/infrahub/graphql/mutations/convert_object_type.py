import ast
from typing import TYPE_CHECKING, Any, Self

from graphene import Boolean, InputObjectType, JSONString, Mutation, String
from graphql import GraphQLResolveInfo
from infrahub_sdk.utils import extract_fields

from infrahub.core.convert_object_type.conversion import InputForDestField, convert_object_type
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class ConvertObjectTypeInput(InputObjectType):
    node_id = String(required=True)
    target_kind = String(required=True)
    # TODO use GenericScalar instead?
    fields_mapping = JSONString(required=True)  # keys are destination attributes/relationships names.
    branch = String(required=True)


class ConvertObjectType(Mutation):
    class Arguments:
        data = ConvertObjectTypeInput(required=True)

    ok = Boolean()
    # TODO Return created node as json?

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: ConvertObjectTypeInput,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        # json.loads doesn't work here as it seems double quotes become single quotes when deserializing server side
        mapping = ast.literal_eval(str(data.fields_mapping))

        fields_mapping: dict[str, InputForDestField] = {}
        for field, input_for_dest_field_str in mapping.items():
            fields_mapping[field] = InputForDestField(**input_for_dest_field_str)

        node_to_convert = await NodeManager.get_one(
            id=str(data.node_id), db=graphql_context.db, branch=str(data.branch)
        )
        new_node = await convert_object_type(
            node=node_to_convert,
            target_kind=str(data.target_kind),
            mapping=fields_mapping,
            branch=graphql_context.branch,
            db=graphql_context.db,
        )

        fields = await extract_fields(info.field_nodes[0].selection_set)
        result: dict[str, Any] = {"ok": True}
        if "object" in fields:
            result["object"] = await new_node.to_graphql(db=graphql_context.db, fields=fields.get("object", {}))
        return cls(**result)

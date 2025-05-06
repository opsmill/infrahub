from typing import TYPE_CHECKING, Any, Self

from graphene import Boolean, InputObjectType, Mutation, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLResolveInfo

from infrahub.core import registry
from infrahub.core.convert_object_type.conversion import InputForDestField, convert_object_type
from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class ConvertObjectTypeInput(InputObjectType):
    node_id = String(required=True)
    target_kind = String(required=True)
    fields_mapping = GenericScalar(required=True)  # keys are destination attributes/relationships names.
    branch = String(required=True)


class ConvertObjectType(Mutation):
    class Arguments:
        data = ConvertObjectTypeInput(required=True)

    ok = Boolean()
    node = GenericScalar()

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        data: ConvertObjectTypeInput,
    ) -> Self:
        """Convert an input node to a given compatible kind."""

        graphql_context: GraphqlContext = info.context

        fields_mapping: dict[str, InputForDestField] = {}
        if not isinstance(data.fields_mapping, dict):
            raise ValueError(f"Expected `fields_mapping` to be a `dict`, got {type(fields_mapping)}")

        for field, input_for_dest_field_str in data.fields_mapping.items():
            fields_mapping[field] = InputForDestField(**input_for_dest_field_str)

        node_to_convert = await NodeManager.get_one(
            id=str(data.node_id), db=graphql_context.db, branch=str(data.branch)
        )
        target_schema = registry.get_node_schema(name=str(data.target_kind), branch=data.branch)
        new_node = await convert_object_type(
            node=node_to_convert,
            target_schema=target_schema,
            mapping=fields_mapping,
            branch=graphql_context.branch,
            db=graphql_context.db,
        )

        dict_node = await new_node.to_graphql(db=graphql_context.db, fields={})
        result: dict[str, Any] = {"ok": True, "node": dict_node}

        return cls(**result)

from typing import TYPE_CHECKING, Any, Self

from graphene import Boolean, InputObjectType, Mutation, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLResolveInfo

from infrahub.core import registry
from infrahub.core.constants.infrahubkind import READONLYREPOSITORY, REPOSITORY
from infrahub.core.convert_object_type.object_conversion import ConversionFieldInput, convert_and_validate_object_type
from infrahub.core.convert_object_type.repository_conversion import convert_repository_type
from infrahub.core.convert_object_type.schema_mapping import get_schema_mapping
from infrahub.core.manager import NodeManager
from infrahub.repositories.create_repository import RepositoryFinalizer

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext


class ConvertObjectTypeInput(InputObjectType):
    node_id = String(required=True)
    target_kind = String(required=True)
    fields_mapping = GenericScalar(required=True)  # keys are destination attributes/relationships names.


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

        node_to_convert = await NodeManager.get_one(
            id=str(data.node_id), db=graphql_context.db, branch=graphql_context.branch
        )

        source_schema = registry.get_node_schema(name=node_to_convert.get_kind(), branch=graphql_context.branch)
        target_schema = registry.get_node_schema(name=str(data.target_kind), branch=graphql_context.branch)

        fields_mapping: dict[str, ConversionFieldInput] = {}
        if not isinstance(data.fields_mapping, dict):
            raise ValueError(f"Expected `fields_mapping` to be a `dict`, got {type(data.fields_mapping)}")

        for field_name, input_for_dest_field_str in data.fields_mapping.items():
            fields_mapping[field_name] = ConversionFieldInput(**input_for_dest_field_str)

        node_to_convert = await NodeManager.get_one(
            id=str(data.node_id), db=graphql_context.db, branch=graphql_context.branch
        )

        # Complete fields mapping with auto-mapping.
        mapping = get_schema_mapping(source_schema=source_schema, target_schema=target_schema)
        for field_name, mapping_value in mapping.items():
            if mapping_value.source_field_name is not None and field_name not in fields_mapping:
                fields_mapping[field_name] = ConversionFieldInput(source_field=mapping_value.source_field_name)

        if target_schema.kind in [REPOSITORY, READONLYREPOSITORY]:
            new_node = await convert_repository_type(
                repository=node_to_convert,
                target_schema=target_schema,
                mapping=fields_mapping,
                branch=graphql_context.branch,
                db=graphql_context.db,
                repository_post_creator=RepositoryFinalizer(
                    account_session=graphql_context.active_account_session,
                    services=graphql_context.active_service,
                    context=graphql_context.get_context(),
                ),
            )
        else:
            new_node = await convert_and_validate_object_type(
                node=node_to_convert,
                target_schema=target_schema,
                mapping=fields_mapping,
                branch=graphql_context.branch,
                db=graphql_context.db,
            )

        dict_node = await new_node.to_graphql(db=graphql_context.db, fields={})
        result: dict[str, Any] = {"ok": True, "node": dict_node}

        return cls(**result)

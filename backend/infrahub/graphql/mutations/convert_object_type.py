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
from infrahub.exceptions import ValidationError
from infrahub.repositories.create_repository import RepositoryFinalizer

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute
    from infrahub.graphql.initialization import GraphqlContext


def _filter_none_values_from_data(input_dict: dict[str, Any]) -> dict[str, Any] | None:
    """Filter out None values from the nested 'data' dict in field mapping input.

    When the UI sends {"data": {"attribute_value": null}}, we need to filter out
    the None value because the Pydantic validator in ConversionFieldValue expects
    exactly one field to be explicitly set with a non-None value.

    If after filtering the 'data' dict is empty, we skip this field mapping entry
    as it indicates the user wants to keep the default behavior.

    Args:
        input_dict: The field mapping input dict, e.g., {"data": {"attribute_value": null}}

    Returns:
        The processed input dict with None values filtered, or None if the input
        should be skipped entirely.
    """
    if not isinstance(input_dict, dict):
        return input_dict

    result = {}
    for key, value in input_dict.items():
        if key == "data" and isinstance(value, dict):
            # Filter out None values from the 'data' dict
            filtered_data = {k: v for k, v in value.items() if v is not None}
            if filtered_data:
                result[key] = filtered_data
            # If filtered_data is empty, we skip adding 'data' key entirely
        else:
            result[key] = value

    # If we have a 'data' key that became empty after filtering, and no other valid keys,
    # return None to indicate this field mapping should be skipped
    if not result or (not result.get("source_field") and not result.get("data") and not result.get("use_default_value")):
        return None

    return result


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
            raise ValidationError(
                input_value=f"Expected `fields_mapping` to be a `dict`, got {type(data.fields_mapping)}"
            )

        for field_name, input_for_dest_field_str in data.fields_mapping.items():
            # Preprocess the input to filter out None values from nested 'data' dict
            # This handles the case where the UI sends {"data": {"attribute_value": null}}
            # which the Pydantic validator would otherwise reject
            processed_input = _filter_none_values_from_data(input_for_dest_field_str)
            if processed_input:
                fields_mapping[field_name] = ConversionFieldInput(**processed_input)

        node_to_convert = await NodeManager.get_one(
            id=str(data.node_id), db=graphql_context.db, branch=graphql_context.branch
        )
        for attribute_name in source_schema.attribute_names:
            attribute: BaseAttribute = getattr(node_to_convert, attribute_name)
            if attribute.is_from_profile:
                raise ValidationError(
                    input_value=f"The attribute '{attribute_name}' is from a profile, converting objects that use profiles is not yet supported."
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

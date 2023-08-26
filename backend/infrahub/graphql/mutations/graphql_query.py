from typing import Optional

from graphene import InputObjectType, Mutation
from graphql import GraphQLResolveInfo

from infrahub.core.schema import NodeSchema
from infrahub.graphql.mutations.main import InfrahubMutationMixin

from .main import InfrahubMutationOptions


class InfrahubGraphQLQueryMutation(InfrahubMutationMixin, Mutation):
    @classmethod
    def __init_subclass_with_meta__(
        cls, schema: NodeSchema = None, _meta=None, **options
    ):  # pylint: disable=arguments-differ
        # Make sure schema is a valid NodeSchema Node Class
        if not isinstance(schema, NodeSchema):
            raise ValueError(f"You need to pass a valid NodeSchema in '{cls.__name__}.Meta', received '{schema}'")

        if not _meta:
            _meta = InfrahubMutationOptions(cls)
        _meta.schema = schema

        super().__init_subclass_with_meta__(_meta=_meta, **options)

    @classmethod
    async def mutate_create(
        cls,
        root: dict,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Optional[str] = None,
        at: Optional[str] = None,
    ):
        # session: AsyncSession = info.context.get("infrahub_session")

        # if query_value := data.get("query", {}).get("value", None):
        #     document: DocumentNode = parse(query_value)
        #     len(document.definitions)
        #     {definition.operation for definition in document.definitions}

        #     result = await extract_schema_models(document.definitions[0].selection_set)

        # operation = get_operation_ast(document, None)

        # errors = validate(self.schema.graphql_schema, document)  # pylint: disable=no-member
        # Validate content of GraphQL Query

        # try:
        #     document: DocumentNode = parse(query)
        #     operation = get_operation_ast(document, operation_name)
        #     errors = validate(self.schema.graphql_schema, document)  # pylint: disable=no-member
        # except GraphQLError as e:
        #     errors = [e]

        obj, result = await super().mutate_create(root=root, info=info, data=data, branch=branch, at=at)

        return obj, result

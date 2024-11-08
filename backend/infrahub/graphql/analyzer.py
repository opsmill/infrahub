from typing import Any, Optional

from graphql import GraphQLSchema, OperationType
from infrahub_sdk.analyzer import GraphQLQueryAnalyzer
from infrahub_sdk.utils import extract_fields

from infrahub.core.branch import Branch
from infrahub.graphql.utils import extract_schema_models


class InfrahubGraphQLQueryAnalyzer(GraphQLQueryAnalyzer):
    def __init__(
        self,
        query: str,
        query_variables: Optional[dict[str, Any]] = None,
        schema: Optional[GraphQLSchema] = None,
        operation_name: Optional[str] = None,
        branch: Optional[Branch] = None,
    ) -> None:
        self.branch: Optional[Branch] = branch
        self.operation_name: Optional[str] = operation_name
        self.query_variables: dict[str, Any] = query_variables or {}
        super().__init__(query=query, schema=schema)

    @property
    def operation_names(self) -> list[str]:
        return [operation.name for operation in self.operations if operation.name is not None]

    async def get_models_in_use(self, types: dict[str, Any]) -> set[str]:
        """List of Infrahub models that are referenced in the query."""
        graphql_types = set()
        models = set()

        if not (self.schema and self.branch):
            raise ValueError("Schema and Branch must be provided to extract the models in use.")

        for definition in self.document.definitions:
            fields = await extract_fields(definition.selection_set)

            operation = getattr(definition, "operation", None)
            if operation == OperationType.QUERY:
                schema = self.schema.query_type
            elif operation == OperationType.MUTATION:
                schema = self.schema.mutation_type
            else:
                # Subscription not supported right now
                continue

            graphql_types.update(await extract_schema_models(fields=fields, schema=schema, root_schema=self.schema))

        for graphql_type_name in graphql_types:
            try:
                graphql_type = types.get(graphql_type_name)
                if not hasattr(graphql_type, "_meta") or not hasattr(graphql_type._meta, "schema"):  # type: ignore[union-attr]
                    continue
                models.add(graphql_type._meta.schema.kind)  # type: ignore[union-attr]
            except ValueError:
                continue

        return models

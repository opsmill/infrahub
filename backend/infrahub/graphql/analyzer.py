from typing import Any, Dict, Optional, Set

from graphql import (
    GraphQLSchema,
    OperationType,
)
from infrahub_sdk.analyzer import GraphQLQueryAnalyzer
from infrahub_sdk.utils import extract_fields

from infrahub.core.branch import Branch
from infrahub.graphql.utils import extract_schema_models


class InfrahubGraphQLQueryAnalyzer(GraphQLQueryAnalyzer):
    def __init__(self, query: str, schema: Optional[GraphQLSchema] = None, branch: Optional[Branch] = None):
        self.branch: Optional[Branch] = branch
        super().__init__(query=query, schema=schema)

    async def get_models_in_use(self, types: Dict[str, Any]) -> Set[str]:
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

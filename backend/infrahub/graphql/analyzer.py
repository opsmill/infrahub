from typing import List, Optional, Set, Tuple

from graphql import (
    DocumentNode,
    GraphQLError,
    GraphQLSchema,
    OperationType,
    parse,
    validate,
)

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.graphql.utils import extract_fields, extract_schema_models


class GraphQLQueryAnalyzer:
    def __init__(self, query: str, schema: Optional[GraphQLSchema] = None, branch: Optional[Branch] = None):
        self.query: str = query
        self.schema: Optional[GraphQLSchema] = schema
        self.branch: Optional[Branch] = branch
        self.document: DocumentNode = parse(self.query)

    @property
    def is_valid(self) -> Tuple[bool, Optional[List[GraphQLError]]]:
        errors = validate(schema=self.schema, document_ast=self.document)
        if len(errors):
            return False, errors

        return True, None

    @property
    def nbr_queries(self) -> int:
        return len(self.document.definitions)

    @property
    def query_types(self) -> Set[str]:
        return {definition.operation for definition in self.document.definitions}

    async def get_fields(self) -> dict:
        fields = {}
        for definition in self.document.definitions:
            fields.update(await extract_fields(definition.selection_set))

        return fields

    async def get_models_in_use(self):
        graphql_types = set()
        models = set()
        # TODO Check if schema AND branch are present

        for definition in self.document.definitions:
            fields = await extract_fields(definition.selection_set)

            if definition.operation == OperationType.QUERY:
                schema = self.schema.query_type
            elif definition.operation == OperationType.MUTATION:
                schema = self.schema.mutation_type
            else:
                # Subscription not supported right now
                continue

            graphql_types.update(await extract_schema_models(fields=fields, schema=schema, root_schema=self.schema))

        for graphql_type_name in graphql_types:
            graphql_type = registry.get_graphql_type(name=graphql_type_name, branch=self.branch)
            if not hasattr(graphql_type._meta, "schema"):
                continue
            models.add(graphql_type._meta.schema.kind)

        return models

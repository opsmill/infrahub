from typing import Any, Dict, List, Optional, Set, Tuple

from graphql import (
    DocumentNode,
    FieldNode,
    GraphQLError,
    GraphQLSchema,
    OperationDefinitionNode,
    OperationType,
    parse,
    validate,
)
from pydantic.v1 import BaseModel

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.graphql.utils import (
    calculate_dict_depth,
    calculate_dict_height,
    extract_fields,
    extract_schema_models,
)


class GraphQLQueryVariable(BaseModel):
    name: str
    type: str
    required: bool = False
    default_value: Optional[Any] = None


class GraphQLOperation(BaseModel):
    name: Optional[str] = None
    operation_type: OperationType


class GraphQLQueryAnalyzer:
    def __init__(self, query: str, schema: Optional[GraphQLSchema] = None, branch: Optional[Branch] = None):
        self.query: str = query
        self.schema: Optional[GraphQLSchema] = schema
        self.branch: Optional[Branch] = branch
        self.document: DocumentNode = parse(self.query)
        self._fields: Optional[Dict] = None

    @property
    def is_valid(self) -> Tuple[bool, Optional[List[GraphQLError]]]:
        errors = validate(schema=self.schema, document_ast=self.document)
        if errors:
            return False, errors

        return True, None

    @property
    def nbr_queries(self) -> int:
        return len(self.document.definitions)

    @property
    def operations(self) -> List[GraphQLOperation]:
        operations = []
        for definition in self.document.definitions:
            if not isinstance(definition, OperationDefinitionNode):
                continue
            operation_type = definition.operation
            for field_node in definition.selection_set.selections:
                if not isinstance(field_node, FieldNode):
                    continue
                operations.append(GraphQLOperation(operation_type=operation_type, name=field_node.name.value))
        return operations

    @property
    def contains_mutation(self) -> bool:
        return any(op.operation_type == OperationType.MUTATION for op in self.operations)

    @property
    def variables(self) -> List[GraphQLQueryVariable]:
        response = []
        for definition in self.document.definitions:
            variable_definitions = getattr(definition, "variable_definitions", None)
            if not variable_definitions:
                continue
            for variable in variable_definitions:
                data = {"name": variable.variable.name.value}
                non_null = False
                if variable.type.kind == "non_null_type":
                    data["type"] = variable.type.type.name.value
                    non_null = True
                else:
                    data["type"] = variable.type.name.value

                if variable.default_value:
                    if data["type"] == "Int":
                        data["default_value"] = int(variable.default_value.value)
                    else:
                        data["default_value"] = variable.default_value.value

                if not data.get("default_value", None) and non_null:
                    data["required"] = True

                response.append(GraphQLQueryVariable(**data))

        return response

    async def calculate_depth(self) -> int:
        """Number of nested levels in the query"""
        fields = await self.get_fields()
        return calculate_dict_depth(data=fields)

    async def calculate_height(self) -> int:
        """Total number of fields requested in the query"""
        fields = await self.get_fields()
        return calculate_dict_height(data=fields)

    async def get_fields(self) -> Dict[str, Any]:
        if not self._fields:
            fields = {}
            for definition in self.document.definitions:
                fields.update(await extract_fields(definition.selection_set))
            self._fields = fields
        return self._fields

    async def get_models_in_use(self) -> Set[str]:
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
                graphql_type = registry.get_graphql_type(name=graphql_type_name, branch=self.branch)
                if not hasattr(graphql_type._meta, "schema"):
                    continue
                models.add(graphql_type._meta.schema.kind)
            except ValueError:
                continue

        return models

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Union

VARIABLE_TYPE_MAPPING = (
    (str, "String!"),
    (int, "Int!"),
    (float, "Float!"),
    (bool, "Boolean!"),
)

SAFE_VALUE = re.compile(r"(^[\$ a-zA-Z0-9_-]+$)|(^$)")


def convert_to_graphql_as_string(value: Union[str, bool, list]) -> str:
    if isinstance(value, str) and value.startswith("$"):
        return value
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool):
        return repr(value).lower()
    if isinstance(value, list):
        values_as_string = [convert_to_graphql_as_string(item) for item in value]
        return "[" + ", ".join(values_as_string) + "]"

    return str(value)


def render_variables_to_string(data: Dict[str, type[Union[str, int, float, bool]]]) -> str:
    """Render a dict into a variable string that will be used in a GraphQL Query.

    The $ sign will be automatically added to the name of the query.
    """
    vars_dict = {}
    for key, value in data.items():
        for class_type, var_string in VARIABLE_TYPE_MAPPING:
            if value == class_type:
                vars_dict[f"${key}"] = var_string

    return ", ".join([f"{key}: {value}" for key, value in vars_dict.items()])


def render_query_block(data: dict, offset: int = 4, indentation: int = 4) -> List[str]:
    FILTERS_KEY = "@filters"
    KEYWORDS_TO_SKIP = [FILTERS_KEY]

    offset_str = " " * offset
    lines = []
    for key, value in data.items():
        if key in KEYWORDS_TO_SKIP:
            continue
        if value is None:
            lines.append(f"{offset_str}{key}")
        elif isinstance(value, dict):
            if "@filters" in value:
                filters_str = ", ".join(
                    [f"{key}: {convert_to_graphql_as_string(value)}" for key, value in value[FILTERS_KEY].items()]
                )
                lines.append(f"{offset_str}{key}({filters_str}) " + "{")
            else:
                lines.append(f"{offset_str}{key} " + "{")

            lines.extend(render_query_block(data=value, offset=offset + indentation, indentation=indentation))
            lines.append(offset_str + "}")

    return lines


MUTATION_GRAPHQL_QUERY_CREATE = """
mutation($name: String!, $description: String!, $query: String!) {
  graphql_query_create(data: {
    name: { value: $name },
    description: { value: $description },
    query: { value: $query }}
    )
    {
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""


class BaseGraphQLQuery:
    query_type: str = "not-defined"
    indentation: int = 4

    def __init__(self, query: dict, variables: Optional[Dict] = None, name: Optional[str] = None):
        self.query = query
        self.variables = variables or {}
        self.name = name or ""

    def render_first_line(self) -> str:
        first_line = self.query_type

        if self.name:
            first_line += self.name

        if self.variables:
            first_line += f" ({render_variables_to_string(self.variables)})"
        first_line += " {"

        return first_line


class Query(BaseGraphQLQuery):
    query_type = "query"

    def render(self) -> str:
        lines = [self.render_first_line()]
        lines.extend(render_query_block(data=self.query, indentation=self.indentation, offset=self.indentation))
        lines.append("}")

        return "\n" + "\n".join(lines) + "\n"


class Mutation(BaseGraphQLQuery):
    query_type = "mutation"

    def __init__(self, *args: Any, mutation: str, input_data: dict, **kwargs: Any):
        self.input_data = input_data
        self.mutation = mutation
        super().__init__(*args, **kwargs)
        self.variable_values: dict[str, Any] = {}

    def render(self) -> str:
        lines = []
        lines.append(" " * self.indentation + f"{self.mutation}(")
        lines.extend(
            self.render_input_block(data=self.input_data, indentation=self.indentation, offset=self.indentation * 2)
        )
        lines.append(" " * self.indentation + "){")
        lines.extend(render_query_block(data=self.query, indentation=self.indentation, offset=self.indentation * 2))
        lines.append(" " * self.indentation + "}")
        lines.append("}")

        lines.insert(0, self.render_first_line())

        return "\n" + "\n".join(lines) + "\n"

    def process_value(self, key: str, value: Union[str, int, bool, list]) -> str:
        if isinstance(value, bool):
            return repr(value).lower()
        if isinstance(value, list):
            values_as_string = [self.process_value(key, item) for item in value]
            return "[" + ", ".join(values_as_string) + "]"

        if isinstance(value, int):
            return str(value)

        if SAFE_VALUE.match(value):
            return f'"{value}"'

        var_name = f"{key}_{uuid.uuid4().hex}"
        self.variables[var_name] = type(value)
        self.variable_values[var_name] = value

        return f"${var_name}"

    def render_input_block(self, data: dict, offset: int = 4, indentation: int = 4) -> List[str]:
        offset_str = " " * offset
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{offset_str}{key}: " + "{")
                lines.extend(self.render_input_block(data=value, offset=offset + indentation, indentation=indentation))
                lines.append(offset_str + "}")
            elif isinstance(value, list):
                lines.append(f"{offset_str}{key}: " + "[")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{offset_str}{' '*indentation}" + "{")
                        lines.extend(
                            self.render_input_block(
                                data=item, offset=offset + indentation + indentation, indentation=indentation
                            )
                        )
                        lines.append(f"{offset_str}{' '*indentation}" + "},")
                    else:
                        lines.append(f"{offset_str}{' '*indentation}{self.process_value(key, value)},")
                lines.append(offset_str + "]")
            else:
                lines.append(f"{offset_str}{key}: {self.process_value(key, value)}")
        return lines

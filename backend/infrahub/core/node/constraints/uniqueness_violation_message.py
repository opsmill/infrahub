from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.template.exceptions import JinjaTemplateError

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core.constants.schema import SchemaElementPathType

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch


class UniquenessViolationMessageBuilder:
    """Format a uniqueness-violation message.

    Names the input attributes that drive any computed field involved, so the user knows
    which value to change.
    """

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    def build(self, node_schema: MainSchemaTypes, fields: list[str]) -> str:
        message = f"Violates uniqueness constraint '{'-'.join(fields)}'"
        inputs = self._collect_computed_inputs(node_schema=node_schema, fields=fields)
        if inputs:
            message += f" (computed from: {', '.join(inputs)})"
        return message

    def _collect_computed_inputs(self, node_schema: MainSchemaTypes, fields: list[str]) -> list[str]:
        allowed_path_types = (
            SchemaElementPathType.ATTR_WITH_PROP
            | SchemaElementPathType.REL_ONE_MANDATORY_ATTR_WITH_PROP
            | SchemaElementPathType.REL_ONE_OPTIONAL_ATTR_WITH_PROP
        )
        inputs: list[str] = []
        for field in fields:
            attr_schema = node_schema.get_attribute_or_none(name=field)
            if attr_schema is None or attr_schema.computed_attribute is None:
                continue
            template = attr_schema.computed_attribute.jinja2_template
            if not template:
                continue
            try:
                variables = InfrahubJinja2Template(template=template).get_variables()
            except JinjaTemplateError:
                continue
            for variable in variables:
                try:
                    attribute_path = self.schema_branch.validate_schema_path(
                        node_schema=node_schema, path=variable, allowed_path_types=allowed_path_types
                    )
                except ValueError:
                    continue
                if attribute_path.is_type_relationship:
                    input_name = (
                        f"{attribute_path.active_relationship_schema.name}"
                        f".{attribute_path.active_attribute_schema.name}"
                    )
                elif attribute_path.is_type_attribute:
                    input_name = attribute_path.active_attribute_schema.name
                else:
                    continue
                if input_name not in inputs:
                    inputs.append(input_name)
        return inputs

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.template.exceptions import JinjaTemplateError

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core.constants.schema import SchemaElementPathType

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

_ALLOWED_INPUT_PATH_TYPES = (
    SchemaElementPathType.ATTR_WITH_PROP
    | SchemaElementPathType.REL_ONE_MANDATORY_ATTR_WITH_PROP
    | SchemaElementPathType.REL_ONE_OPTIONAL_ATTR_WITH_PROP
)


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
        """Return the deduplicated user-controllable inputs feeding the computed fields among `fields`."""
        inputs: list[str] = []
        for field in fields:
            for input_name in self._inputs_for_field(node_schema=node_schema, field=field):
                if input_name not in inputs:
                    inputs.append(input_name)
        return inputs

    def _inputs_for_field(self, node_schema: MainSchemaTypes, field: str) -> list[str]:
        """Resolve the input names a single field's Jinja2 template depends on, or empty if not computed."""
        attr_schema = node_schema.get_attribute_or_none(name=field)
        if attr_schema is None or attr_schema.computed_attribute is None:
            return []
        template = attr_schema.computed_attribute.jinja2_template
        if not template:
            return []
        try:
            variables = InfrahubJinja2Template(template=template).get_variables()
        except JinjaTemplateError:
            return []
        names: list[str] = []
        for variable in variables:
            input_name = self._resolve_input_name(node_schema=node_schema, path=variable)
            if input_name is not None:
                names.append(input_name)
        return names

    def _resolve_input_name(self, node_schema: MainSchemaTypes, path: str) -> str | None:
        """Map a Jinja2 path to a user-facing name: a bare attribute (`model`) or dotted relationship (`owner.name`)."""
        try:
            attribute_path = self.schema_branch.validate_schema_path(
                node_schema=node_schema, path=path, allowed_path_types=_ALLOWED_INPUT_PATH_TYPES
            )
        except ValueError:
            return None
        if attribute_path.is_type_relationship:
            return f"{attribute_path.active_relationship_schema.name}.{attribute_path.active_attribute_schema.name}"
        if attribute_path.is_type_attribute:
            return attribute_path.active_attribute_schema.name
        return None

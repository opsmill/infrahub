from typing import Optional, Union

from infrahub.core.attribute_path.parser import AttributePathParser
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.exceptions import ValidationError


class DisplayLabelRenderer:
    def __init__(self, attribute_path_parser: AttributePathParser):
        self.attribute_path_parser = attribute_path_parser

    async def render(self, node: Node, branch: Optional[Union[Branch, str]]) -> str:
        schema = node.get_schema()
        display_labels = schema.display_labels
        if not display_labels:
            return repr(node)

        display_elements = []
        for attribute_path_str in display_labels:
            parsed_attribute_path = self.attribute_path_parser.parse(schema, attribute_path_str, branch)
            if not parsed_attribute_path.attribute_property_name:
                raise ValidationError("Display Label must be of the form <attribute_name>__<property_name>")

            if parsed_attribute_path.relationship_schema:
                raise ValidationError("Only attributes can be used in Display Label, not relationships")

            attr = getattr(node, parsed_attribute_path.attribute_schema.name)
            display_elements.append(str(getattr(attr, parsed_attribute_path.attribute_property_name)))

        display_label = " ".join(display_elements)
        if display_label.strip() == "":
            return repr(node)
        return display_label.strip()

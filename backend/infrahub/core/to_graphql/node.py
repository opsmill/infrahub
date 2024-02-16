from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

from infrahub.core.display_label.renderer import DisplayLabelRenderer
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest

if TYPE_CHECKING:
    from infrahub.core.attribute import BaseAttribute


class ToGraphQLNodeTranslator(ToGraphQLTranslatorInterface[Node]):
    def __init__(self, display_label_renderer: DisplayLabelRenderer):
        self.display_label_renderer = display_label_renderer

    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, Node)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        """Generate GraphQL Payload for all attributes

        Returns:
            (dict): Return GraphQL Payload
        """
        node = to_graphql_request.obj
        response: dict[str, Any] = {"id": node.id, "type": node.get_kind()}

        if to_graphql_request.related_node_ids is not None:
            to_graphql_request.related_node_ids.add(node.id)

        FIELD_NAME_TO_EXCLUDE = ["id"] + node.get_schema().relationship_names

        if to_graphql_request.fields and isinstance(to_graphql_request.fields, dict):
            field_names = [
                field_name for field_name in to_graphql_request.fields.keys() if field_name not in FIELD_NAME_TO_EXCLUDE
            ]
        else:
            field_names = node.get_schema().attribute_names + ["__typename", "display_label"]

        for field_name in field_names:
            if field_name == "__typename":
                response[field_name] = node.get_kind()
                continue

            if field_name == "display_label":
                response[field_name] = await self.display_label_renderer.render(node, node.get_branch())
                continue

            if field_name == "_updated_at":
                updated_at = node.get_updated_at()
                if updated_at and isinstance(updated_at, Timestamp):
                    response[field_name] = updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            field: Optional[BaseAttribute] = getattr(node, field_name, None)

            if not field:
                response[field_name] = None
                continue
            if to_graphql_request.fields and isinstance(to_graphql_request.fields, dict):
                new_request = to_graphql_request.model_copy(
                    update={"obj": field, "fields": to_graphql_request.fields.get(field_name)}
                )
            else:
                new_request = to_graphql_request.model_copy(update={"obj": field, "fields": {}})
            response[field_name] = await translate_function(new_request)
        return response

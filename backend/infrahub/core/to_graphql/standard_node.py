from typing import Any, Awaitable, Callable, Dict

from infrahub.core.node.standard import StandardNode

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class ToGraphQLStandardNodeTranslator(ToGraphQLTranslatorInterface[StandardNode]):
    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, StandardNode)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        node = to_graphql_request.obj
        response = {"id": node.uuid}

        if not to_graphql_request.fields:
            return response
        for field_name in to_graphql_request.fields.keys():
            if field_name in ["id"]:
                continue
            if field_name == "__typename":
                response[field_name] = node.get_type()
                continue
            field = getattr(node, field_name)
            if field is None:
                response[field_name] = None
                continue
            response[field_name] = field

        return response

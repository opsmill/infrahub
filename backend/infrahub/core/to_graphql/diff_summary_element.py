from typing import Any, Awaitable, Callable, Dict

from infrahub.core.diff_model import DiffSummaryElement

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class ToGraphQLDiffSummaryTranslator(ToGraphQLTranslatorInterface[DiffSummaryElement]):
    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, DiffSummaryElement)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        return {
            "branch": to_graphql_request.obj.branch,
            "node": to_graphql_request.obj.node,
            "kind": to_graphql_request.obj.kind,
            "actions": [action.value for action in to_graphql_request.obj.actions],
        }

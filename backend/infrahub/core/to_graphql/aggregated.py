from typing import Any, Dict, List

from .exception import NoGraphQLTranslatorError
from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class AggregatedToGraphQLTranslators:
    def __init__(self, translators: List[ToGraphQLTranslatorInterface]):
        self.translators = translators

    async def to_graphql(
        self,
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        translated = None
        for translator in self.translators:
            if translator.supports(to_graphql_request.obj):
                return await translator.to_graphql(
                    self.to_graphql,
                    to_graphql_request,
                )
        if not translated:
            raise NoGraphQLTranslatorError(
                f"No GraphQLTranslator class for object of type {type(to_graphql_request.obj).__name__}"
            )

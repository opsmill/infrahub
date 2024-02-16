from typing import Any, Awaitable, Callable, Dict

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.relationship import RelationshipManager

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class ToGraphQLRelationshipManagerTranslator(ToGraphQLTranslatorInterface[RelationshipManager]):
    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, RelationshipManager)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        # NOTE Need to investigate when and why we are passing the peer directly here, how do we account for many relationship
        manager = to_graphql_request.obj

        if manager.schema.cardinality == RelationshipCardinality.MANY:
            raise TypeError("to_graphql is not available for relationship with multiple cardinality")

        relationships = await manager.get_relationships(db=to_graphql_request.db)
        if not relationships:
            return {}

        new_request = to_graphql_request.model_copy(update={"obj": relationships[0]})
        return await translate_function(new_request)

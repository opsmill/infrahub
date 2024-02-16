from typing import Any, Awaitable, Callable, Dict

from infrahub.core.constants.schema import FlagProperty, NodeProperty
from infrahub.core.relationship import PREFIX_PROPERTY, Relationship
from infrahub.core.timestamp import Timestamp

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class ToGraphQLRelationshipTranslator(ToGraphQLTranslatorInterface[Relationship]):
    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, Relationship)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        """Generate GraphQL Payload for the associated Peer."""
        relationship = to_graphql_request.obj
        node_properties = [np.value for np in NodeProperty]
        flag_properties = [fp.value for fp in FlagProperty]

        peer_fields, rel_fields = {}, {}
        if to_graphql_request.fields:
            peer_fields = {
                key: value
                for key, value in to_graphql_request.fields.items()
                if not key.startswith(PREFIX_PROPERTY) or not key == "__typename"
            }
            rel_fields = {
                key.replace(PREFIX_PROPERTY, ""): value
                for key, value in to_graphql_request.fields.items()
                if key.startswith(PREFIX_PROPERTY)
            }

        peer = await relationship.get_peer(db=to_graphql_request.db)
        new_request = to_graphql_request.model_copy(update={"obj": peer, "fields": peer_fields})
        response = await translate_function(new_request)

        for field_name in rel_fields.keys():
            if field_name == "updated_at":
                if relationship.updated_at and isinstance(relationship.updated_at, Timestamp):
                    response[f"{PREFIX_PROPERTY}{field_name}"] = relationship.updated_at.to_graphql()

            if field_name in node_properties:
                node_prop_getter = getattr(relationship, f"get_{field_name}")
                node_prop = await node_prop_getter(db=to_graphql_request.db)
                if not node_prop:
                    response[f"{PREFIX_PROPERTY}{field_name}"] = None
                else:
                    new_request = to_graphql_request.model_copy(
                        update={"obj": node_prop, "fields": rel_fields[field_name]}
                    )
                    response[f"{PREFIX_PROPERTY}{field_name}"] = await translate_function(new_request)
            if field_name in flag_properties:
                response[f"{PREFIX_PROPERTY}{field_name}"] = getattr(relationship, field_name)

        if to_graphql_request.fields and "__typename" in to_graphql_request.fields:
            response["__typename"] = f"Related{peer.get_kind()}"

        return response

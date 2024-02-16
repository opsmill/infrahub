from enum import Enum
from typing import Any, Awaitable, Callable, Dict

from infrahub.core.attribute import BaseAttribute
from infrahub.core.constants.schema import FlagProperty, NodeProperty
from infrahub.core.timestamp import Timestamp

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class ToGraphQLAttributeTranslator(ToGraphQLTranslatorInterface[BaseAttribute]):
    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, BaseAttribute)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        """Generate GraphQL Payload for this attribute."""
        # pylint: disable=too-many-branches

        attribute = to_graphql_request.obj

        response: dict[str, Any] = {
            "id": attribute.id,
        }

        if to_graphql_request.fields and isinstance(to_graphql_request.fields, dict):
            field_names = list(to_graphql_request.fields.keys())
        else:
            # REMOVED updated_at for now, need to investigate further how it's being used today
            field_names = (
                ["__typename", "value"] + [fp.value for fp in FlagProperty] + [np.value for np in NodeProperty]
            )

        for field_name in field_names:
            if field_name == "updated_at":
                if attribute.updated_at and isinstance(attribute.updated_at, Timestamp):
                    response[field_name] = attribute.updated_at.to_graphql()
                else:
                    response[field_name] = None
                continue

            if field_name == "__typename":
                response[field_name] = attribute.get_kind()
                continue

            if field_name in ["source", "owner"]:
                node_attr_getter = getattr(attribute, f"get_{field_name}")
                node_attr = await node_attr_getter(db=to_graphql_request.db)
                if not node_attr:
                    response[field_name] = None
                elif to_graphql_request.fields and isinstance(to_graphql_request.fields, dict):
                    new_request = to_graphql_request.model_copy(
                        update={"obj": node_attr, "fields": to_graphql_request.fields[field_name]}
                    )
                else:
                    new_request = to_graphql_request.model_copy(
                        update={
                            "obj": node_attr,
                            "fields": {"id": None, "display_label": None, "__typename": None},
                        }
                    )
                response[field_name] = await translate_function(new_request)
                continue

            if field_name.startswith("_"):
                field = getattr(attribute, field_name[1:])
            else:
                field = getattr(attribute, field_name)

            if field_name == "value" and isinstance(field, Enum):
                field = field.name
            if isinstance(field, str):
                response[field_name] = self._filter_sensitive(
                    value=field,
                    attribute_kind=attribute.get_kind(),
                    filter_sensitive=to_graphql_request.filter_sensitive,
                )
            elif isinstance(field, (int, bool, dict, list)):
                response[field_name] = field

        return response

    def _filter_sensitive(self, value: str, attribute_kind: str, filter_sensitive: bool) -> str:
        if filter_sensitive and attribute_kind in ["HashedPassword", "Password"]:
            return "***"

        return value

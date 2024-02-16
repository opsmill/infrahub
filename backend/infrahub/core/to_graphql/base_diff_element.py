from enum import Enum
from typing import Any, Awaitable, Callable, Dict

from pydantic import BaseModel

from infrahub.core.diff_model import BaseDiffElement
from infrahub.core.timestamp import Timestamp

from .interface import ToGraphQLTranslatorInterface
from .model import ToGraphQLRequest


class ToGraphQLDiffTranslator(ToGraphQLTranslatorInterface[BaseDiffElement]):
    def supports(self, object_to_translate: Any) -> bool:
        return isinstance(object_to_translate, BaseDiffElement)

    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        """Recursively Export the model to a dict for GraphQL.
        The main rules of convertion are:
            - Ignore the fields mark as exclude=True
            - Convert the Dict in List
        """
        resp: Dict[str, Any] = {}
        for key, value in to_graphql_request.obj:
            if isinstance(value, BaseModel):
                resp[key] = value.to_graphql()  # type: ignore[attr-defined]
            elif isinstance(value, dict):
                resp[key] = [item.to_graphql() for item in value.values()]
            elif to_graphql_request.obj.__fields__[key].field_info.exclude:
                continue
            elif isinstance(value, Enum):
                resp[key] = value.value
            elif isinstance(value, Timestamp):
                resp[key] = value.to_string()
            else:
                resp[key] = value

        return resp

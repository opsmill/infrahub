from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, Generic, TypeVar

from .model import ToGraphQLRequest

T = TypeVar("T")


class ToGraphQLTranslatorInterface(ABC, Generic[T]):
    @abstractmethod
    def supports(self, object_to_translate: Any) -> bool:
        ...

    @abstractmethod
    async def to_graphql(
        self,
        translate_function: Callable[[ToGraphQLRequest], Awaitable[Dict[str, Any]]],
        to_graphql_request: ToGraphQLRequest,
    ) -> Dict[str, Any]:
        ...

from typing import Any

from typing_extensions import Self


class InfrahubObjectStorage:
    @classmethod
    async def init(cls, **kwargs: Any) -> Self:
        return cls(**kwargs)

    async def store(self, identifier: str, content: bytes) -> None:
        raise NotImplementedError

    async def retrieve(self, identifier: str) -> str:
        raise NotImplementedError

from typing_extensions import Self


class InfrahubObjectStorage:
    @classmethod
    async def init(cls, **kwargs) -> Self:
        return cls(**kwargs)

    async def store(self, identifier: str, content: bytes):
        raise NotImplementedError

    async def retrieve(self, identifier: str):
        raise NotImplementedError

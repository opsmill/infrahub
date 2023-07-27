from typing_extensions import Self


class InfrahubObjectStorage:
    def __init__(self, settings: dict):
        self.settings = settings

    @classmethod
    async def init(cls, **kwargs) -> Self:
        return cls(**kwargs)

    async def store(self, identifier: str, content: str):
        raise NotImplementedError

    async def retrieve(self, identifier: str):
        raise NotImplementedError

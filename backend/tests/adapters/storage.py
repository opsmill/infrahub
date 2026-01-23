from typing import BinaryIO

from infrahub.storage import InfrahubObjectStorage


class DummyObjectStorage(InfrahubObjectStorage):
    """In-memory storage backend for testing."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def store(self, identifier: str, content: BinaryIO) -> None:
        self._files[identifier] = content.read()

    def retrieve(self, identifier: str) -> str:
        return self._files[identifier].decode()

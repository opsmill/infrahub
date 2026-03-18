from typing import BinaryIO

from infrahub.exceptions import NodeNotFoundError
from infrahub.storage import InfrahubObjectStorage


class DummyObjectStorage(InfrahubObjectStorage):
    """In-memory storage backend for testing."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def store(self, identifier: str, content: BinaryIO) -> None:
        self._files[identifier] = content.read()

    def retrieve(self, identifier: str) -> str:
        if identifier not in self._files:
            raise NodeNotFoundError(node_type="StorageObject", identifier=identifier)
        return self._files[identifier].decode()

    def retrieve_binary(self, identifier: str) -> bytes:
        if identifier not in self._files:
            raise NodeNotFoundError(node_type="StorageObject", identifier=identifier)
        return self._files[identifier]

    def delete(self, identifier: str) -> None:
        self._files.pop(identifier, None)

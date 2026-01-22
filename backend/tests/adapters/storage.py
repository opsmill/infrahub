from infrahub.storage import InfrahubObjectStorage


class DummyObjectStorage(InfrahubObjectStorage):
    """In-memory storage backend for testing."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def store(self, identifier: str, content: bytes) -> None:
        self._files[identifier] = content

    def retrieve(self, identifier: str) -> str:
        return self._files[identifier].decode()

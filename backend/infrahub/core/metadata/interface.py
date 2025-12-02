from abc import abstractmethod

from infrahub.core.timestamp import Timestamp


class MetadataInterface:
    @abstractmethod
    def _set_created_at(self, value: Timestamp | None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _set_created_by(self, value: str | None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _set_updated_at(self, value: Timestamp | None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _set_updated_by(self, value: str | None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _get_created_at(self) -> Timestamp | None:
        raise NotImplementedError()

    @abstractmethod
    def _get_created_by(self) -> str | None:
        raise NotImplementedError()

    @abstractmethod
    def _get_updated_at(self) -> Timestamp | None:
        raise NotImplementedError()

    @abstractmethod
    def _get_updated_by(self) -> str | None:
        raise NotImplementedError()

from typing import Any, Protocol


class WorkerLiveness(Protocol):
    async def list_active_worker_ids(self) -> set[str]:
        """Return the ids of the workers currently reporting an active heartbeat."""
        ...


class InfrahubLogger(Protocol):
    def debug(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send a debug event."""

    def info(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send an info event."""

    def warning(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event."""

    def error(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""

    def critical(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    def exception(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""

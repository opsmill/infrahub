from typing import Any


class FakeLogger:
    def __init__(self) -> None:
        self.info_logs: list[str | None] = []
        self.error_logs: list[str | None] = []

    def debug(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send a debug event"""

    def info(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        self.info_logs.append(event)

    def warning(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    def error(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""
        self.error_logs.append(event)

    def critical(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    def exception(self, event: str | None = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""

from typing import Any, Optional


class FakeLogger:
    def __init__(self) -> None:
        self.info_logs: list[Optional[str]] = []
        self.error_logs: list[Optional[str]] = []

    def debug(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a debug event"""

    def info(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        self.info_logs.append(event)

    def warning(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    def error(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""
        self.error_logs.append(event)

    def critical(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    def exception(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""


class FakeTaskReportLogger:
    def __init__(self) -> None:
        self.info_logs: list[Optional[str]] = []
        self.error_logs: list[Optional[str]] = []

    async def info(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an info event."""
        self.info_logs.append(event)

    async def warning(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a warning event"""

    async def error(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an error event."""
        self.error_logs.append(event)

    async def critical(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send a critical event."""

    async def exception(self, event: Optional[str] = None, *args: Any, **kw: Any) -> Any:
        """Send an exception event."""

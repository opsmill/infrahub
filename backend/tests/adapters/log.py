from typing import Any, List, Optional


class FakeLogger:
    def __init__(self) -> None:
        self.info_logs: List[Optional[str]] = []
        self.error_logs: List[Optional[str]] = []

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

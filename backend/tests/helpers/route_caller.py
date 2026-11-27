from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import TracebackType


class NoDatabaseSession:
    """The session a route opens when a test calls it as a function: it hands out nothing to query."""

    async def __aenter__(self) -> Any:
        return None

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        return None


class NoDatabase:
    """The database of the application when nothing in a test reads it."""

    def start_session(self) -> NoDatabaseSession:
        return NoDatabaseSession()


CALLER_REQUEST: Any = SimpleNamespace(
    app=SimpleNamespace(state=SimpleNamespace(service=SimpleNamespace(cache=None), db=NoDatabase()))
)
"""What a route reads from the request when a test calls it as a function: the cache of the merge write blocker, and
the database it opens a session on."""
CALLER_ACCOUNT: Any = SimpleNamespace(account_id="caller")
"""The account a route reads the identifier of when a test calls it as a function."""

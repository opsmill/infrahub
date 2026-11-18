from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode

if TYPE_CHECKING:
    from types import TracebackType


class SessionUsage:
    """How many database sessions are open right now and the most that were open at once."""

    def __init__(self) -> None:
        self.open_sessions = 0
        self.max_open_sessions = 0

    def opened(self) -> None:
        self.open_sessions += 1
        self.max_open_sessions = max(self.max_open_sessions, self.open_sessions)

    def closed(self) -> None:
        self.open_sessions -= 1


class SessionTrackingInfrahubDatabase(InfrahubDatabase):
    """Database that records how many of its sessions are open at the same time."""

    def __init__(self, session_usage: SessionUsage | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # shared by reference so the sessions derived from this database report into the same tally
        self.session_usage = session_usage if session_usage is not None else SessionUsage()

    @classmethod
    def from_db(cls, db: InfrahubDatabase) -> SessionTrackingInfrahubDatabase:
        """Build a session-tracking database on the driver of an existing one."""
        return cls(
            mode=InfrahubDatabaseMode.DRIVER,
            driver=db._driver,
            db_type=db.db_type,
            default_neo4j_runtime=db.default_neo4j_runtime,
            queries_names_to_config=db.queries_names_to_config,
        )

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["session_usage"] = self.session_usage
        return ctx

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if self.is_session:
            self.session_usage.opened()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if self.is_session:
            self.session_usage.closed()

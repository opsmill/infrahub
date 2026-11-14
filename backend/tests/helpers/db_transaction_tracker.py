from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from infrahub.database import InfrahubDatabase, InfrahubDatabaseMode

if TYPE_CHECKING:
    from types import TracebackType


class TransactionUsage:
    """How many database transactions are open right now."""

    def __init__(self) -> None:
        self.open_transactions = 0


class TransactionTrackingInfrahubDatabase(InfrahubDatabase):
    """Database that records how many of its transactions are open."""

    def __init__(self, transaction_usage: TransactionUsage | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # shared by reference so the sessions and transactions derived from this database report into the same tally
        self.transaction_usage = transaction_usage if transaction_usage is not None else TransactionUsage()

    @classmethod
    def from_db(cls, db: InfrahubDatabase) -> TransactionTrackingInfrahubDatabase:
        """Build a transaction-tracking database on the driver of an existing one."""
        return cls(
            mode=InfrahubDatabaseMode.DRIVER,
            driver=db._driver,
            db_type=db.db_type,
            default_neo4j_runtime=db.default_neo4j_runtime,
            queries_names_to_config=db.queries_names_to_config,
        )

    def get_context(self) -> dict[str, Any]:
        ctx = super().get_context()
        ctx["transaction_usage"] = self.transaction_usage
        return ctx

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if self.is_transaction:
            self.transaction_usage.open_transactions += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await super().__aexit__(exc_type, exc_value, traceback)
        if self.is_transaction:
            self.transaction_usage.open_transactions -= 1

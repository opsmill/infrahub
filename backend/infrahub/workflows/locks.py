from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

from infrahub.worker import WORKER_IDENTITY


@dataclass
class GCLDefinition:
    """Definition for a Global Concurrency Limit."""

    prefix: str
    limit: int
    per_worker: bool = False  # If True, appends WORKER_IDENTITY to name

    def get_name(self) -> str:
        """Get the full GCL name, including worker identity if per_worker."""
        if self.per_worker:
            return f"{self.prefix}:{WORKER_IDENTITY}"
        return self.prefix

    def get_pattern(self) -> re.Pattern[str]:
        """Get regex pattern to match GCL names of this type."""
        if self.per_worker:
            return re.compile(rf"^{re.escape(self.prefix)}:(.+)$")
        return re.compile(rf"^{re.escape(self.prefix)}$")

    async def create(self, client: PrefectClient) -> None:
        """Create/upsert this GCL."""
        await client.upsert_global_concurrency_limit_by_name(
            name=self.get_name(),
            limit=self.limit,
        )


# GCL Definitions
COMPUTED_ATTR_BATCH_GCL = GCLDefinition(
    prefix="computed-attr-batch",
    limit=1,
    per_worker=True,
)

# All per-worker GCLs that need cleanup
PER_WORKER_GCLS = [
    COMPUTED_ATTR_BATCH_GCL,
]

from infrahub.services.protocols import WorkerLiveness


class StaticWorkerLiveness(WorkerLiveness):
    """Reports a fixed set of active workers, with no heartbeats or cache involved."""

    def __init__(self, active_worker_ids: set[str]) -> None:
        self.active_worker_ids = active_worker_ids

    async def list_active_worker_ids(self) -> set[str]:
        return self.active_worker_ids

from infrahub import lock


class MergeLocker:
    lock_namespace = "merge"

    def __init__(self) -> None:
        self.lock_registry = lock.registry

    def acquire_global_lock(self) -> lock.InfrahubLock:
        return self.lock_registry.get(name="all_branches", namespace=self.lock_namespace)

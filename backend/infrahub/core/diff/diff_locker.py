from infrahub import lock


class DiffLocker:
    lock_namespace = "diff-update"

    def __init__(self) -> None:
        self.lock_registry = lock.registry

    def get_lock_name(self, base_branch_name: str, diff_branch_name: str, is_incremental: bool) -> str:
        lock_name = f"{base_branch_name}__{diff_branch_name}"
        if is_incremental:
            lock_name += "__incremental"
        return lock_name

    def get_existing_lock(
        self, target_branch_name: str, source_branch_name: str, is_incremental: bool = False
    ) -> lock.InfrahubLock | None:
        name = self.get_lock_name(target_branch_name, source_branch_name, is_incremental)
        return self.lock_registry.get_existing(name=name, namespace=self.lock_namespace)

    def acquire_lock(
        self, target_branch_name: str, source_branch_name: str, is_incremental: bool = False
    ) -> lock.InfrahubLock:
        name = self.get_lock_name(target_branch_name, source_branch_name, is_incremental)
        return self.lock_registry.get(name=name, namespace=self.lock_namespace)

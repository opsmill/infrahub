from dataclasses import dataclass


@dataclass
class NumberPoolLockDefinition:
    pool_id: str

    @property
    def lock_name(self) -> str:
        return f"number-pool-creation-{self.pool_id}"

    @property
    def namespace_name(self) -> str:
        return "number-pool"

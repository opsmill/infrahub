from dataclasses import dataclass


@dataclass
class NumberPoolLockDefinition:
    schema_kind: str
    attribute_name: str

    @property
    def lock_name(self) -> str:
        return f"number-pool-creation-{self.schema_kind}-{self.attribute_name}"

    @property
    def namespace_name(self) -> str:
        return "number-pool"

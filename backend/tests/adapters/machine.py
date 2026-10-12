from dataclasses import dataclass

GIBIBYTE = 1024**3


@dataclass(frozen=True)
class FixedMachine:
    """A machine whose figures are fixed, so a reading can be checked against exact numbers."""

    name: str = "test-host"
    processors: int | None = 18
    pinned_processors: int | None = None
    total_memory: int = 64 * GIBIBYTE
    free_memory: int = 48 * GIBIBYTE

    def hostname(self) -> str:
        return self.name

    def processor_count(self) -> int | None:
        return self.processors

    def pinned_processor_count(self) -> int | None:
        return self.pinned_processors

    def memory_total(self) -> int:
        return self.total_memory

    def memory_available(self) -> int:
        return self.free_memory

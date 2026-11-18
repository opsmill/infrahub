"""How many processes share this process's container."""

import os

PROCESSES_PER_CONTAINER_ENV = "INFRAHUB_INTERNAL_PROCESSES_PER_CONTAINER"


def processes_per_container() -> int:
    """Return how many processes share this container, 1 when the count is missing or invalid."""
    try:
        count = int(os.environ.get(PROCESSES_PER_CONTAINER_ENV, ""))
    except ValueError:
        return 1
    return count if count > 0 else 1

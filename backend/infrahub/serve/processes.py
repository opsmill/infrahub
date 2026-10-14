"""How many processes share this process's container."""

import os

# Set by the gunicorn worker class, not by an operator, so the app knows how many processes gunicorn starts.
PROCESSES_PER_CONTAINER_ENV = "INFRAHUB_INTERNAL_PROCESSES_PER_CONTAINER"


def processes_per_container() -> int:
    """Return how many processes share this process's container.

    Gunicorn starts several API server processes in one container and records their
    number in the environment of each. A process that gunicorn did not start, such as
    a task worker, runs alone, so the count is 1 when the value is missing or is not a
    positive whole number.
    """
    try:
        count = int(os.environ.get(PROCESSES_PER_CONTAINER_ENV, ""))
    except ValueError:
        return 1
    return count if count > 0 else 1

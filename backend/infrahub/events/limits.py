import os

_DEFAULT_MAX_RELATED_RESOURCES = 500
_MIN_RUN_CONTEXT_HEADROOM = 20


def get_prefect_max_related_resources() -> int:
    """Return the maximum number of related resources the Prefect API accepts per event.

    The value is read from the environment on every call, falling back to the
    default when the variable is unset, malformed, or not a positive number.
    """
    raw_value = os.environ.get("PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES", "")
    try:
        max_related_resources = int(raw_value)
    except ValueError:
        return _DEFAULT_MAX_RELATED_RESOURCES
    if max_related_resources <= 0:
        return _DEFAULT_MAX_RELATED_RESOURCES
    return max_related_resources


def get_related_resource_budget() -> int:
    """Return the number of related resources an event may still carry when it leaves Infrahub.

    Prefect's events worker appends run-context resources to an event after it has been handed
    over - flow run, task run, flow, deployment, work queue, work pool, and one per flow-run tag -
    by extending the list in place, which does not re-run the client-side validation. An event
    that leaves on the maximum therefore arrives above it, and the Prefect API answers by closing
    the event stream rather than by dropping the single event. The budget stays below the maximum
    so the enlarged event is still accepted.
    """
    maximum = get_prefect_max_related_resources()
    return max(1, maximum - max(_MIN_RUN_CONTEXT_HEADROOM, maximum // 10))


def get_submission_chunk_size() -> int:
    """Return the maximum number of node ids to carry in one recompute submission.

    A coalesced recompute passes the union of changed node ids as a flow-run parameter, which
    Prefect caps at a fixed serialized size. Half the related-resource maximum keeps each
    submission well under that cap and keeps the reader query it feeds small.
    """
    return max(1, get_prefect_max_related_resources() // 2)

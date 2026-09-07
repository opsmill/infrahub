from prefect.settings import PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES

# Prefect's own default for the maximum, used when the effective setting cannot be honoured. The
# Infrahub image raises the setting well above this, but that is the image's choice rather than
# Prefect's default, so it must not be the fallback: a deployment that does not set it is held to
# this value by Prefect, and assuming the image's larger one got those events rejected in silence.
PREFECT_DEFAULT_MAX_RELATED_RESOURCES = 100

# Six fixed entries - flow run, task run, flow, deployment, work queue, work pool - plus one per
# flow-run tag. Only tags present when the run was created reach an event: a run refreshes its tags
# once before its context is entered, so anything a flow tags itself with later stays out. Infrahub
# renders four tag kinds today; the rest of the allowance absorbs tags added later.
MAX_RUN_CONTEXT_RESOURCES = 6 + 14


def get_prefect_max_related_resources() -> int:
    """Return the maximum number of related resources the Prefect API accepts per event.

    The value is read from the effective Prefect setting on every call, so it follows however the
    operator configured Prefect - either environment variable name, a profile, or a configuration
    file - rather than only the one variable the image happens to set. This is the same accessor
    Prefect's own `Event` validator compares against, so the cap Infrahub truncates to cannot
    drift away from the cap Prefect enforces.

    A non-positive setting falls back to the default. That does not keep events flowing - Prefect
    rejects every event carrying a related resource once its maximum is zero, whatever Infrahub
    does - it only leaves the budget and chunk size below derived from a sensible ceiling rather
    than from a meaningless one. A setting that is not a number never reaches here: Prefect refuses
    to build its settings from it and the process fails to start, which is deliberate, since
    silently substituting a different ceiling is the failure this module exists to prevent.
    """
    max_related_resources = PREFECT_EVENTS_MAXIMUM_RELATED_RESOURCES.value()
    if max_related_resources <= 0:
        return PREFECT_DEFAULT_MAX_RELATED_RESOURCES
    return max_related_resources


def get_related_resource_budget() -> int:
    """Return the number of related resources an event may still carry when it leaves Infrahub.

    Prefect's events worker appends run-context resources to an event after it has been handed
    over, by extending the list in place, which does not re-run the client-side validation. An
    event that leaves on the maximum therefore arrives above it, and the Prefect API answers by
    closing the event stream rather than by dropping the single event. The budget stays below the
    maximum so the enlarged event is still accepted.

    The reservation is a tenth of the maximum, never less than what the append can add.
    """
    maximum = get_prefect_max_related_resources()
    return max(1, maximum - max(MAX_RUN_CONTEXT_RESOURCES, maximum // 10))


def get_submission_chunk_size() -> int:
    """Return the maximum number of node ids to carry in one recompute submission.

    A coalesced recompute passes the union of changed node ids as a flow-run parameter, which
    Prefect caps at a fixed serialized size. Half the related-resource maximum keeps each
    submission well under that cap and keeps the reader query it feeds small.
    """
    return max(1, get_prefect_max_related_resources() // 2)

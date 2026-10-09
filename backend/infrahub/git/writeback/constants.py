DELIVERY_RETRIES: int = 3
# Prefect accepts the delays only as a list.
DELIVERY_RETRY_DELAYS_SECONDS: list[float] = [30, 120, 300]

FETCH_TIMEOUT_SECONDS: int = 120
PUSH_TIMEOUT_SECONDS: int = 300
LOCAL_GIT_TIMEOUT_SECONDS: int = 120

# Exceeds the longest retry delay plus the fetch and push timeouts.
STALE_AFTER_SECONDS: int = 15 * 60

REMOVED_ENTRY_IDS_KEPT: int = 256

# Covers a whole automatic retry chain whose fetches and pushes end at their time limits, plus ten minutes for
# the import and the queue update; a fetch or a push that hangs can outlast it.
NARROWED_HOLD_TTL_SECONDS: int = (
    int(sum(DELIVERY_RETRY_DELAYS_SECONDS))
    + (DELIVERY_RETRIES + 1) * (FETCH_TIMEOUT_SECONDS + PUSH_TIMEOUT_SECONDS)
    + 10 * 60
)
NARROWED_HOLD_MAX_BYTES: int = 512 * 1024

RELEASE_LEASE_SECONDS: int = 15 * 60

# An acquire that its time limit cancels after the lock key is set leaves the lock held until this time ends.
STATE_LOCK_TTL_SECONDS: int = 30
STATE_LOCK_ACQUIRE_SECONDS: int = 10

# With these delays, the last try starts after the state lock of a dead worker has expired.
ENQUEUE_RETRIES: int = 3
ENQUEUE_RETRY_DELAYS_SECONDS: tuple[float, ...] = (2, 8, 20)
BARRIER_STATE_READ_RETRIES: int = 3
BARRIER_STATE_READ_DELAYS_SECONDS: tuple[float, ...] = (2, 8, 20)

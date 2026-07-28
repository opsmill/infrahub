from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.log import InfrahubLogger


@contextmanager
def merge_follow_up_guard(log: InfrahubLogger, message: str) -> Iterator[None]:
    """Isolate a follow-up that runs once a merge or rebase is already committed.

    The committed state can no longer be rolled back when the follow-up runs, so any error it raises is
    logged and absorbed instead of propagated: letting it escape would report an already-committed
    operation as failed. Only wrap blocks whose sole effect on failure is to be logged and skipped --
    a block that must react to the failure (set a flag, fall back) has to handle it explicitly.
    """
    try:
        yield
    except Exception:
        log.exception(message)

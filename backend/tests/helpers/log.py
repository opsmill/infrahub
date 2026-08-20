"""Install the infrahub.log traceback suppression filter for a test, then remove it again."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from infrahub.log import PREFECT_RUN_LOGGERS, install_traceback_suppression_filter

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub.log import TracebackSuppressionFilter


@contextmanager
def traceback_suppression() -> Iterator[TracebackSuppressionFilter]:
    """Register the traceback filter on the Prefect run loggers, as production startup does, then remove it."""
    traceback_filter = install_traceback_suppression_filter()
    try:
        yield traceback_filter
    finally:
        for prefect_logger_name in PREFECT_RUN_LOGGERS:
            logging.getLogger(prefect_logger_name).removeFilter(traceback_filter)

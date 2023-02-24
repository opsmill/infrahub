"""Helpful APIs for setting up DiffSync logging.

Copyright (c) 2020 Network To Code, LLC <info@networktocode.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging
from importlib.util import find_spec

import structlog  # type: ignore
from packaging import version


def enable_console_logging(verbosity=0):
    """Enable formatted logging to console with the specified verbosity.

    See https://www.structlog.org/en/stable/development.html as a reference

    Args:
        verbosity (int): 0 for WARNING logs, 1 for INFO logs, 2 for DEBUG logs
    """
    if verbosity == 0:
        logging.basicConfig(format="%(message)s", level=logging.WARNING)
    elif verbosity == 1:
        logging.basicConfig(format="%(message)s", level=logging.INFO)
    else:
        logging.basicConfig(format="%(message)s", level=logging.DEBUG)

    processors = [
        structlog.stdlib.filter_by_level,  # <-- added
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M.%S"),
        structlog.processors.StackInfoRenderer(),
    ]

    if _structlog_exception_formatter_required():
        processors.append(structlog.processors.format_exc_info)

    # ConsoleRenderer must be added after format_exc_info
    processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _structlog_exception_formatter_required():
    """Determine if structlog exception formatter is needed.

    Return True if structlog exception formatter should be loaded
    into structlog processors.

    Structlog version 21.2.0 or higher will generate a warning
    if either rich or better_exceptions packages are available to import
    when the 'format_exc_info' processor is used.

    This code snippet will determine if we need to add 'format_exc_info'
    to the processors.
    """
    if version.parse(structlog.__version__) < version.Version("21.2.0"):
        return True

    # Determine if module is available for import, without importing it.
    rich = find_spec("rich")
    better_exceptions = find_spec("better_exceptions")
    return not (rich or better_exceptions)

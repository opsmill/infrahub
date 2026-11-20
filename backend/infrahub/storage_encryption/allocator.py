"""Make the C allocator give back the buffers of the files that the migration encrypts.

With glibc, a threshold decides whether a large buffer is a separate memory block or part of the memory area of the
thread that asked for it. A separate block goes back to the operating system when it is freed. Memory taken from a
thread area stays in the process, and glibc raises the threshold by itself (up to 32 MiB) after it frees a large
block, so after the first file the buffers of files of about 1 to 32 MiB come from the areas of the threads. Every
thread that encrypted such a file then keeps about twice the size of the file for as long as the process runs.

Fixing the threshold at 1 MiB, the same as the environment variable `MALLOC_MMAP_THRESHOLD_=1048576`, keeps every
buffer of 1 MiB or more in a separate block. The call only exists in glibc: on any other platform or C library
nothing is changed. A threshold that the operator sets in the environment is kept as it is.
"""

from __future__ import annotations

import ctypes
import os
import sys
from functools import cache
from typing import TYPE_CHECKING, Protocol

from infrahub.log import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

log = get_logger()

M_MMAP_THRESHOLD = -3
"""Number of the parameter "threshold for a separate memory block" in `mallopt`, from glibc's `malloc.h`."""
MMAP_THRESHOLD_BYTES = 1024 * 1024
"""Size from which a buffer is a separate memory block."""
THRESHOLD_VARIABLE = "MALLOC_MMAP_THRESHOLD_"
"""Environment variable with which glibc reads the same threshold at the start of the process."""
TUNABLES_VARIABLE = "GLIBC_TUNABLES"
TUNABLE_NAME = "glibc.malloc.mmap_threshold"
"""The glibc tunable that sets the same threshold. `GLIBC_TUNABLES` lists tunables as `name=value`, separated by colons."""


class Mallopt(Protocol):
    """The `mallopt` function of glibc: sets a parameter of the allocator and returns 1 when it accepts the value."""

    def __call__(self, parameter: int, value: int, /) -> int: ...


def _load_mallopt() -> Mallopt:
    function = ctypes.CDLL("libc.so.6").mallopt
    function.argtypes = (ctypes.c_int, ctypes.c_int)
    function.restype = ctypes.c_int
    return function


def _gnu_libc_version() -> str | None:
    """Return the version of glibc, or None when the C library is not glibc (musl refuses the name)."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        return os.confstr("CS_GNU_LIBC_VERSION")
    except (ValueError, OSError):
        return None


def operator_set_threshold(environ: Mapping[str, str]) -> bool:
    """Whether the environment already sets the threshold, in which case the operator's value is kept."""
    if THRESHOLD_VARIABLE in environ:
        return True
    return any(entry.split("=", 1)[0] == TUNABLE_NAME for entry in environ.get(TUNABLES_VARIABLE, "").split(":"))


def set_mmap_threshold(
    libc_version: str | None, environ: Mapping[str, str], load_mallopt: Callable[[], Mallopt]
) -> bool:
    """Fix the threshold for a separate memory block at 1 MiB.

    Returns True when glibc accepted the value. Returns False, and changes nothing, when the C library is not glibc
    (`libc_version` is None) or when the environment sets the threshold. A failure of the call is logged and returns
    False: the migration goes on and the process keeps memory as it did before.
    """
    if libc_version is None:
        return False
    if operator_set_threshold(environ):
        log.info("The memory block threshold is set in the environment and is kept")
        return False
    try:
        accepted = load_mallopt()(M_MMAP_THRESHOLD, MMAP_THRESHOLD_BYTES) == 1
    except (OSError, AttributeError, ctypes.ArgumentError) as exc:
        log.warning("The memory block threshold of the process could not be set", error=str(exc))
        return False
    if not accepted:
        log.warning("The memory block threshold of the process was refused by the C library")
    return accepted


@cache
def fix_mmap_threshold() -> bool:
    """Fix the threshold of this process; the first call does it and the later calls return its result."""
    return set_mmap_threshold(libc_version=_gnu_libc_version(), environ=os.environ, load_mallopt=_load_mallopt)

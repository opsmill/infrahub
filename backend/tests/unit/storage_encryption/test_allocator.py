from __future__ import annotations

import os
import subprocess  # noqa: S404 - the check runs a fresh interpreter
import sys
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from structlog.testing import capture_logs

from infrahub.storage_encryption import allocator

if TYPE_CHECKING:
    from collections.abc import Mapping

MIB = 1024 * 1024
THREADS = 8
BUFFER_MIB = 10
GLIBC = "glibc 2.41"
SUBPROCESS_TIMEOUT_SECONDS = 120

HOLD_AND_FREE_IN_THREADS = textwrap.dedent(
    f"""
    import sys, threading

    if sys.argv[1] == "fix":
        from infrahub.storage_encryption.allocator import fix_mmap_threshold
        assert fix_mmap_threshold()

    def anonymous_mib():
        with open("/proc/self/status") as status:
            return next(int(line.split()[1]) for line in status if line.startswith("RssAnon:")) / 1024

    warm_up = b"w" * ({BUFFER_MIB} * {MIB})
    del warm_up
    before = anonymous_mib()
    everyone_holds = threading.Barrier({THREADS})

    def work():
        content = b"x" * ({BUFFER_MIB} * {MIB})
        sealed = content + b"y"
        everyone_holds.wait()
        del content, sealed

    threads = [threading.Thread(target=work) for _ in range({THREADS})]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    print(round(anonymous_mib() - before))
    """
)


class RecordingMallopt:
    """Stands in for the `mallopt` function of glibc: keeps the calls and answers what it was told to."""

    def __init__(self, answer: int) -> None:
        self.answer = answer
        self.calls: list[tuple[int, int]] = []

    def __call__(self, parameter: int, value: int, /) -> int:
        self.calls.append((parameter, value))
        return self.answer


class Loader:
    """Stands in for the loading of the C library: keeps how often it was asked for, and fails when told to."""

    def __init__(self, mallopt: RecordingMallopt, failure: Exception | None = None) -> None:
        self.mallopt = mallopt
        self.failure = failure
        self.loads = 0

    def __call__(self) -> RecordingMallopt:
        self.loads += 1
        if self.failure is not None:
            raise self.failure
        return self.mallopt


@dataclass
class SetCase:
    name: str
    libc_version: str | None
    environ: Mapping[str, str]
    expected_calls: list[tuple[int, int]]
    expected_result: bool


SET_CASES = [
    SetCase(
        name="glibc and an empty environment fix the threshold at one mebibyte",
        libc_version=GLIBC,
        environ={},
        expected_calls=[(-3, 1048576)],
        expected_result=True,
    ),
    SetCase(
        name="a C library that is not glibc is left alone",
        libc_version=None,
        environ={},
        expected_calls=[],
        expected_result=False,
    ),
    SetCase(
        name="the threshold variable of the operator is kept",
        libc_version=GLIBC,
        environ={"MALLOC_MMAP_THRESHOLD_": "4194304"},
        expected_calls=[],
        expected_result=False,
    ),
    SetCase(
        name="the threshold tunable of the operator is kept",
        libc_version=GLIBC,
        environ={"GLIBC_TUNABLES": "glibc.malloc.trim_threshold=1048576:glibc.malloc.mmap_threshold=4194304"},
        expected_calls=[],
        expected_result=False,
    ),
    SetCase(
        name="a tunable whose name only starts like the threshold tunable does not stop the call",
        libc_version=GLIBC,
        environ={"GLIBC_TUNABLES": "glibc.malloc.mmap_threshold_backup=4194304"},
        expected_calls=[(-3, 1048576)],
        expected_result=True,
    ),
    SetCase(
        name="a tunable whose name ends like the threshold tunable does not stop the call",
        libc_version=GLIBC,
        environ={"GLIBC_TUNABLES": "x.glibc.malloc.mmap_threshold=4194304"},
        expected_calls=[(-3, 1048576)],
        expected_result=True,
    ),
    SetCase(
        name="another tunable does not stop the call",
        libc_version=GLIBC,
        environ={"GLIBC_TUNABLES": "glibc.malloc.arena_max=2"},
        expected_calls=[(-3, 1048576)],
        expected_result=True,
    ),
]


@pytest.mark.parametrize("case", SET_CASES, ids=lambda case: case.name)
def test_set_mmap_threshold_calls_the_allocator_only_when_it_may(case: SetCase) -> None:
    mallopt = RecordingMallopt(answer=1)

    result = allocator.set_mmap_threshold(
        libc_version=case.libc_version, environ=case.environ, load_mallopt=Loader(mallopt=mallopt)
    )

    assert (result, mallopt.calls) == (case.expected_result, case.expected_calls)


def test_the_c_library_is_not_loaded_when_it_is_not_glibc() -> None:
    loader = Loader(mallopt=RecordingMallopt(answer=1))

    allocator.set_mmap_threshold(libc_version=None, environ={}, load_mallopt=loader)

    assert loader.loads == 0


def test_a_refusal_of_the_allocator_is_logged_and_reported() -> None:
    loader = Loader(mallopt=RecordingMallopt(answer=0))

    with capture_logs() as logs:
        result = allocator.set_mmap_threshold(libc_version=GLIBC, environ={}, load_mallopt=loader)

    assert result is False
    assert [(entry["log_level"], entry["event"]) for entry in logs] == [
        ("warning", "The memory block threshold of the process was refused by the C library")
    ]


@pytest.mark.parametrize(
    "failure",
    [OSError("libc.so.6: cannot open shared object file"), AttributeError("undefined symbol: mallopt")],
    ids=["library_missing", "symbol_missing"],
)
def test_a_library_that_cannot_be_used_is_logged_and_does_not_raise(failure: Exception) -> None:
    loader = Loader(mallopt=RecordingMallopt(answer=1), failure=failure)

    with capture_logs() as logs:
        result = allocator.set_mmap_threshold(libc_version=GLIBC, environ={}, load_mallopt=loader)

    assert result is False
    assert [(entry["log_level"], entry["event"], entry["error"]) for entry in logs] == [
        ("warning", "The memory block threshold of the process could not be set", str(failure))
    ]


def test_the_threshold_of_the_operator_is_logged_as_kept() -> None:
    with capture_logs() as logs:
        allocator.set_mmap_threshold(
            libc_version=GLIBC,
            environ={"MALLOC_MMAP_THRESHOLD_": "4194304"},
            load_mallopt=Loader(mallopt=RecordingMallopt(answer=1)),
        )

    assert [(entry["log_level"], entry["event"]) for entry in logs] == [
        ("info", "The memory block threshold is set in the environment and is kept")
    ]


def clean_environment() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in {allocator.THRESHOLD_VARIABLE, allocator.TUNABLES_VARIABLE}}


def kept_mib(mode: str) -> int:
    run = subprocess.run(  # noqa: S603
        [sys.executable, "-c", HOLD_AND_FREE_IN_THREADS, mode],
        capture_output=True,
        text=True,
        check=True,
        env=clean_environment(),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    return int(run.stdout.strip())


@pytest.mark.skipif(
    allocator._gnu_libc_version() is None, reason="the call exists only in glibc, and the memory is read from /proc"
)
def test_threads_that_held_large_buffers_do_not_keep_them_once_the_threshold_is_fixed() -> None:
    kept_by_default = kept_mib("default")
    if kept_by_default < THREADS * BUFFER_MIB:
        pytest.skip("this version of glibc gives large buffers back without the setting")

    assert kept_mib("fix") < THREADS * BUFFER_MIB // 4

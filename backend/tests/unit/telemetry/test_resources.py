"""Unit tests for the per-process resource reader.

The reader parses the container control group (cgroup v2 first, then v1) for the
enforced CPU quota and the memory limit, and falls back to the machine's own
figures when no control group is present. Every case is driven from fixture
files under a temporary cgroup root, on a machine whose CPU count, pinned CPUs
and memory are fixed, so every figure is checked against an exact number and
nothing is read from the machine running the tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.telemetry.resources import ProcessResources, WorkerResourceReading
from tests.adapters.machine import GIBIBYTE, FixedMachine

if TYPE_CHECKING:
    from pathlib import Path


MACHINE = FixedMachine()
"""18 CPUs, none pinned, 64 GiB of which 48 GiB are free."""

PROCESSES_PER_CONTAINER = 4


def _write_cgroup_files(cgroup_root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = cgroup_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def _reader(
    tmp_path: Path, files: dict[str, str], proc_content: str = "0::/\n", machine: FixedMachine = MACHINE
) -> ProcessResources:
    """A reader over limit files under ``tmp_path``, for a container shared by four processes."""
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir(exist_ok=True)
    _write_cgroup_files(cgroup_root, files)
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text(proc_content)
    return ProcessResources(
        machine=machine,
        processes_per_container=PROCESSES_PER_CONTAINER,
        cgroup_root=cgroup_root,
        proc_cgroup=proc_cgroup,
    )


@dataclass
class CpuCase:
    name: str
    files: dict[str, str]
    expected_assigned: int | None
    expected_available: int | None
    machine: FixedMachine = MACHINE


CPU_CASES = [
    CpuCase(
        name="v2_limited",
        files={"cpu.max": "400000 100000"},
        expected_assigned=4,
        expected_available=4,
    ),
    CpuCase(
        name="v2_unlimited_reports_the_machine",
        files={"cpu.max": "max 100000"},
        expected_assigned=None,
        expected_available=18,
    ),
    CpuCase(
        name="v2_fractional_rounds_assigned_up_and_available_down",
        files={"cpu.max": "150000 100000"},
        expected_assigned=2,
        expected_available=1,
    ),
    CpuCase(
        name="v1_limited",
        files={"cpu/cpu.cfs_quota_us": "200000", "cpu/cpu.cfs_period_us": "100000"},
        expected_assigned=2,
        expected_available=2,
    ),
    CpuCase(
        name="v1_unlimited_sentinel_reports_the_machine",
        files={"cpu/cpu.cfs_quota_us": "-1", "cpu/cpu.cfs_period_us": "100000"},
        expected_assigned=None,
        expected_available=18,
    ),
    CpuCase(
        name="v1_fractional_rounds_assigned_up_and_available_down",
        files={"cpu/cpu.cfs_quota_us": "250000", "cpu/cpu.cfs_period_us": "100000"},
        expected_assigned=3,
        expected_available=2,
    ),
    CpuCase(
        name="v2_single_core",
        files={"cpu.max": "100000 100000"},
        expected_assigned=1,
        expected_available=1,
    ),
    CpuCase(
        name="v2_sub_core_quota_still_counts_one_usable_cpu",
        files={"cpu.max": "25000 100000"},
        expected_assigned=1,
        expected_available=1,
    ),
    CpuCase(
        name="v2_quota_above_the_machine_is_capped_by_the_machine",
        files={"cpu.max": "102400000 100000"},
        expected_assigned=1024,
        expected_available=18,
    ),
    CpuCase(
        name="missing_files_report_the_machine",
        files={},
        expected_assigned=None,
        expected_available=18,
    ),
    CpuCase(
        name="pinning_without_a_limit_caps_available",
        files={},
        machine=FixedMachine(pinned_processors=2),
        expected_assigned=None,
        expected_available=2,
    ),
    CpuCase(
        name="a_limit_tighter_than_the_pinning_wins",
        files={"cpu.max": "400000 100000"},
        machine=FixedMachine(pinned_processors=8),
        expected_assigned=4,
        expected_available=4,
    ),
    CpuCase(
        name="pinning_alone_when_the_machine_reports_no_cpu_count",
        files={},
        machine=FixedMachine(processors=None, pinned_processors=3),
        expected_assigned=None,
        expected_available=3,
    ),
    CpuCase(
        name="nothing_known_leaves_available_unknown",
        files={},
        machine=FixedMachine(processors=None),
        expected_assigned=None,
        expected_available=None,
    ),
]


@pytest.mark.parametrize("case", CPU_CASES, ids=[case.name for case in CPU_CASES])
def test_cpu_figures(case: CpuCase, tmp_path: Path) -> None:
    reading = _reader(tmp_path, case.files, machine=case.machine).read()

    assert reading.processor_assigned == case.expected_assigned
    assert reading.processor_available == case.expected_available


@dataclass
class MemoryCase:
    name: str
    files: dict[str, str]
    expected_total: int
    expected_available: int


MEMORY_CASES = [
    MemoryCase(
        name="v2_limited",
        files={"memory.max": "8589934592", "memory.current": "1073741824"},
        expected_total=8589934592,
        expected_available=8589934592 - 1073741824,
    ),
    MemoryCase(
        name="v1_limited",
        files={
            "memory/memory.limit_in_bytes": "8589934592",
            "memory/memory.usage_in_bytes": "2147483648",
        },
        expected_total=8589934592,
        expected_available=8589934592 - 2147483648,
    ),
    MemoryCase(
        name="v2_limit_lowered_below_current_usage_clamps_to_zero",
        files={"memory.max": "1073741824", "memory.current": "2147483648"},
        expected_total=1073741824,
        expected_available=0,
    ),
    MemoryCase(
        name="v2_unlimited_falls_back_to_the_machine",
        files={"memory.max": "max"},
        expected_total=64 * GIBIBYTE,
        expected_available=48 * GIBIBYTE,
    ),
    MemoryCase(
        name="v1_unlimited_sentinel_falls_back_to_the_machine",
        files={"memory/memory.limit_in_bytes": "9223372036854771712"},
        expected_total=64 * GIBIBYTE,
        expected_available=48 * GIBIBYTE,
    ),
    MemoryCase(
        name="missing_files_fall_back_to_the_machine",
        files={},
        expected_total=64 * GIBIBYTE,
        expected_available=48 * GIBIBYTE,
    ),
]


@pytest.mark.parametrize("case", MEMORY_CASES, ids=[case.name for case in MEMORY_CASES])
def test_cgroup_memory(case: MemoryCase, tmp_path: Path) -> None:
    reading = _reader(tmp_path, case.files).read()

    assert reading.memory_total == case.expected_total
    assert reading.memory_available == case.expected_available


@dataclass
class CgroupPathCase:
    """A process whose control group is resolved from a ``/proc/self/cgroup`` file.

    ``files`` are laid out under the cgroup root, so a path such as
    ``system.slice/app.scope/cpu.max`` places a limit on the process's own
    (non-root) control group, the layout seen without a private cgroup namespace.
    """

    name: str
    proc_content: str
    files: dict[str, str]
    expected_assigned: int | None
    expected_available: int | None
    expected_memory_total: int | None
    expected_memory_available: int | None


CGROUP_PATH_CASES = [
    CgroupPathCase(
        name="host_namespace_reads_the_process_cgroup",
        proc_content="0::/system.slice/app.scope\n",
        files={
            "system.slice/app.scope/cpu.max": "400000 100000",
            "system.slice/app.scope/memory.max": "8589934592",
            "system.slice/app.scope/memory.current": "1073741824",
        },
        expected_assigned=4,
        expected_available=4,
        expected_memory_total=8589934592,
        expected_memory_available=8589934592 - 1073741824,
    ),
    CgroupPathCase(
        name="ancestor_limit_applies_to_an_unlimited_leaf",
        proc_content="0::/kubepods.slice/pod1.slice/container\n",
        files={
            "kubepods.slice/pod1.slice/container/cpu.max": "max 100000",
            "kubepods.slice/pod1.slice/container/memory.max": "max",
            "kubepods.slice/pod1.slice/cpu.max": "200000 100000",
            "kubepods.slice/pod1.slice/memory.max": "4294967296",
            "kubepods.slice/pod1.slice/memory.current": "1073741824",
        },
        expected_assigned=2,
        expected_available=2,
        expected_memory_total=4294967296,
        expected_memory_available=4294967296 - 1073741824,
    ),
    CgroupPathCase(
        name="most_restrictive_level_wins",
        proc_content="0::/a/b\n",
        files={
            "a/b/cpu.max": "400000 100000",
            "a/b/memory.max": "8589934592",
            "a/b/memory.current": "536870912",
            "a/cpu.max": "200000 100000",
            "a/memory.max": "4294967296",
            "a/memory.current": "1073741824",
        },
        expected_assigned=2,
        expected_available=2,
        expected_memory_total=4294967296,
        expected_memory_available=4294967296 - 1073741824,
    ),
    CgroupPathCase(
        # The named folder does not exist, so only the top folder is read and the tighter limits on "a" are ignored.
        name="unresolvable_cgroup_path_falls_back_to_the_root",
        proc_content="0::/a/vanished.scope\n",
        files={
            "cpu.max": "400000 100000",
            "memory.max": "8589934592",
            "memory.current": "1073741824",
            "a/cpu.max": "100000 100000",
            "a/memory.max": "2147483648",
            "a/memory.current": "1073741824",
        },
        expected_assigned=4,
        expected_available=4,
        expected_memory_total=8589934592,
        expected_memory_available=8589934592 - 1073741824,
    ),
    CgroupPathCase(
        # A host v1 hierarchy, where the limits sit under the process's own path
        # within each co-mounted controller rather than at the mount root.
        name="v1_non_root_path_reads_the_process_own_controllers",
        proc_content="12:memory:/system.slice/app.service\n3:cpu,cpuacct:/system.slice/app.service\n",
        files={
            "cpu,cpuacct/system.slice/app.service/cpu.cfs_quota_us": "200000",
            "cpu,cpuacct/system.slice/app.service/cpu.cfs_period_us": "100000",
            "memory/system.slice/app.service/memory.limit_in_bytes": "8589934592",
            "memory/system.slice/app.service/memory.usage_in_bytes": "2147483648",
        },
        expected_assigned=2,
        expected_available=2,
        expected_memory_total=8589934592,
        expected_memory_available=8589934592 - 2147483648,
    ),
    CgroupPathCase(
        # Every v1 level carries the controller files, an unenforced one holding the
        # unlimited sentinel, so the limit on the ancestor slice is what binds.
        name="v1_ancestor_limit_applies_to_an_unlimited_leaf",
        proc_content="12:memory:/system.slice/app.service\n3:cpu,cpuacct:/system.slice/app.service\n",
        files={
            "cpu,cpuacct/system.slice/app.service/cpu.cfs_quota_us": "-1",
            "cpu,cpuacct/system.slice/app.service/cpu.cfs_period_us": "100000",
            "cpu,cpuacct/system.slice/cpu.cfs_quota_us": "400000",
            "cpu,cpuacct/system.slice/cpu.cfs_period_us": "100000",
            "memory/system.slice/app.service/memory.limit_in_bytes": "9223372036854771712",
            "memory/system.slice/app.service/memory.usage_in_bytes": "536870912",
            "memory/system.slice/memory.limit_in_bytes": "4294967296",
            "memory/system.slice/memory.usage_in_bytes": "1073741824",
        },
        expected_assigned=4,
        expected_available=4,
        expected_memory_total=4294967296,
        expected_memory_available=4294967296 - 1073741824,
    ),
]


@pytest.mark.parametrize("case", CGROUP_PATH_CASES, ids=[case.name for case in CGROUP_PATH_CASES])
def test_cgroup_path_resolution(case: CgroupPathCase, tmp_path: Path) -> None:
    reading = _reader(tmp_path, case.files, proc_content=case.proc_content).read()

    assert reading == WorkerResourceReading(
        processes_per_container=PROCESSES_PER_CONTAINER,
        processor_assigned=case.expected_assigned,
        processor_available=case.expected_available,
        memory_total=case.expected_memory_total,
        memory_available=case.expected_memory_available,
    )


def test_a_nearly_full_ancestor_binds_before_a_roomier_leaf_limit(tmp_path: Path) -> None:
    # The leaf carries the smaller limit, but the ancestor's limit is charged against
    # its whole subtree and is nearly exhausted, so it binds first.
    gib = GIBIBYTE
    files = {
        "pod/container/memory.max": str(4 * gib),
        "pod/container/memory.current": str(gib // 2),
        "pod/memory.max": str(5 * gib),
        "pod/memory.current": str(4 * gib + gib // 2 + gib // 10),
    }

    reading = _reader(tmp_path, files, proc_content="0::/pod/container\n").read()

    # Capacity is still the tightest ceiling, the leaf's 4 GiB...
    assert reading.memory_total == 4 * gib
    # ...but only the ancestor's remainder is actually free, not the leaf's 3.5 GiB.
    assert reading.memory_available == 5 * gib - (4 * gib + gib // 2 + gib // 10)


def test_unreadable_usage_file_keeps_the_capacity_figure(tmp_path: Path) -> None:
    # A directory where the usage file belongs fails the read without being absent.
    (tmp_path / "cgroup" / "memory.current").mkdir(parents=True)

    reading = _reader(tmp_path, {"memory.max": "8589934592"}).read()

    assert reading.memory_total == 8589934592
    assert reading.memory_available is None
    assert reading.processor_available == 18


def test_limit_values_refresh_between_reads(tmp_path: Path) -> None:
    # A live reconfiguration (a ``docker update --cpus``, a Kubernetes in-place
    # pod resize) rewrites the cgroup limit files without restarting the process,
    # so the CPU quota and memory capacity must reflect it on the next read
    # rather than staying at whatever was true when the process started.
    reader = _reader(
        tmp_path,
        {"cpu.max": "100000 100000", "memory.max": "8589934592", "memory.current": "1073741824"},
    )

    first = reader.read()
    assert first.processor_assigned == 1
    assert first.memory_total == 8589934592
    assert first.memory_available == 8589934592 - 1073741824

    _write_cgroup_files(
        tmp_path / "cgroup",
        {"cpu.max": "400000 100000", "memory.max": "4294967296", "memory.current": "536870912"},
    )
    second = reader.read()

    assert second.processor_assigned == 4
    assert second.processor_available == 4
    assert second.memory_total == 4294967296
    assert second.memory_available == 4294967296 - 536870912


def test_leaf_cpu_max_absent_still_falls_through_to_ancestor(tmp_path: Path) -> None:
    """A leaf with no ``cpu.max`` file at all (ENOENT) is the normal per-level case.

    An absent file falls through to an ancestor's limit; only a genuine read failure
    stops that fallback.
    """
    (tmp_path / "cgroup" / "a" / "b").mkdir(parents=True)  # leaf exists but carries no cpu.max of its own

    reading = _reader(tmp_path, {"a/cpu.max": "200000 100000"}, proc_content="0::/a/b\n").read()

    assert reading.processor_assigned == 2


def test_unreadable_leaf_cpu_max_reports_unknown_instead_of_ancestor_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A leaf ``cpu.max`` that exists but cannot be read must not be treated as absent.

    Falling through to the ancestor's looser limit would silently overstate the
    component's CPU allocation, so the quota is reported as unknown instead. Using a
    directory where a file is expected is a portable, root-independent way to trigger
    a genuine (non-ENOENT) read failure.
    """
    failing_file = tmp_path / "cgroup" / "a" / "b" / "cpu.max"
    failing_file.mkdir(parents=True)  # a directory, not a file: read raises IsADirectoryError
    reader = _reader(tmp_path, {"a/cpu.max": "200000 100000"}, proc_content="0::/a/b\n")

    with caplog.at_level(logging.WARNING, logger="infrahub.telemetry.resources"):
        reading = reader.read()

    assert reading.processor_assigned is None
    assert reading.processor_available is None
    # The failure is traceable: one warning names the file that could not be used.
    assert [record.levelname for record in caplog.records if str(failing_file) in record.getMessage()] == ["WARNING"]


def test_unreadable_memory_max_reports_unknown_instead_of_ancestor_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    failing_file = tmp_path / "cgroup" / "a" / "b" / "memory.max"
    failing_file.mkdir(parents=True)
    reader = _reader(
        tmp_path, {"a/memory.max": "4294967296", "a/memory.current": "1073741824"}, proc_content="0::/a/b\n"
    )

    with caplog.at_level(logging.WARNING, logger="infrahub.telemetry.resources"):
        reading = reader.read()

    assert reading.memory_total is None
    assert reading.memory_available is None
    assert [record.levelname for record in caplog.records if str(failing_file) in record.getMessage()] == ["WARNING"]


def test_unparseable_leaf_cpu_max_reports_unknown_instead_of_ancestor_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Content that yields no limit is as unknown as a file that will not read.

    A level whose ``cpu.max`` holds something unrecognised has a limit that cannot
    be determined, not a limit that is absent, so falling through to the ancestor
    would overstate the allocation in exactly the way the unreadable case does.
    """
    reader = _reader(tmp_path, {"a/b/cpu.max": "not-a-quota", "a/cpu.max": "200000 100000"}, proc_content="0::/a/b\n")
    failing_file = tmp_path / "cgroup" / "a" / "b" / "cpu.max"

    with caplog.at_level(logging.WARNING, logger="infrahub.telemetry.resources"):
        reading = reader.read()

    assert reading.processor_assigned is None
    assert reading.processor_available is None
    assert [record.levelname for record in caplog.records if str(failing_file) in record.getMessage()] == ["WARNING"]


def test_unparseable_memory_max_reports_unknown_instead_of_ancestor_value(tmp_path: Path) -> None:
    reader = _reader(
        tmp_path,
        {"a/b/memory.max": "eight gigabytes", "a/memory.max": "4294967296", "a/memory.current": "1073741824"},
        proc_content="0::/a/b\n",
    )

    reading = reader.read()

    assert reading.memory_total is None
    assert reading.memory_available is None


def test_unparseable_v1_quota_reports_unknown_instead_of_ancestor_value(tmp_path: Path) -> None:
    reader = _reader(
        tmp_path,
        {
            "cpu,cpuacct/system.slice/app.service/cpu.cfs_quota_us": "",
            "cpu,cpuacct/system.slice/app.service/cpu.cfs_period_us": "100000",
            "cpu,cpuacct/system.slice/cpu.cfs_quota_us": "400000",
            "cpu,cpuacct/system.slice/cpu.cfs_period_us": "100000",
        },
        proc_content="3:cpu,cpuacct:/system.slice/app.service\n",
    )

    reading = reader.read()

    assert reading.processor_assigned is None
    assert reading.processor_available is None


def test_unreadable_cpu_max_does_not_affect_memory_fields(tmp_path: Path) -> None:
    """CPU and memory are collected independently: a CPU-only failure must not null memory."""
    (tmp_path / "cgroup" / "cpu.max").mkdir(parents=True)

    reading = _reader(tmp_path, {"memory.max": "8589934592", "memory.current": "1073741824"}).read()

    assert reading.processor_assigned is None
    assert reading.processor_available is None
    assert reading.memory_total == 8589934592
    assert reading.memory_available == 8589934592 - 1073741824


def test_unreadable_memory_max_does_not_affect_cpu_fields(tmp_path: Path) -> None:
    (tmp_path / "cgroup" / "memory.max").mkdir(parents=True)

    reading = _reader(tmp_path, {"cpu.max": "400000 100000"}).read()

    assert reading.memory_total is None
    assert reading.memory_available is None
    assert reading.processor_assigned == 4
    assert reading.processor_available == 4

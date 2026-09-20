"""Unit tests for the per-process resource reader.

The reader parses the container control group (cgroup v2 first, then v1) for the
enforced CPU quota and the memory limit, and falls back to whole-host figures
from psutil when no control group is present. Every case is driven from fixture
files under a temporary cgroup root, so the cgroup inputs are fixture-isolated
and need no patching; the host's logical CPU count and CPU-affinity mask are
still read live from the real environment for the capping math.
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import psutil
import pytest

from infrahub.telemetry.resources import ProcessResources, _usable_processors

if TYPE_CHECKING:
    from pathlib import Path


def _write_cgroup_files(cgroup_root: Path, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = cgroup_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


@dataclass
class CpuQuotaCase:
    name: str
    files: dict[str, str]
    expected_assigned: int | None


CPU_QUOTA_CASES = [
    CpuQuotaCase(
        name="v2_limited",
        files={"cpu.max": "400000 100000"},
        expected_assigned=4,
    ),
    CpuQuotaCase(
        name="v2_unlimited",
        files={"cpu.max": "max 100000"},
        expected_assigned=None,
    ),
    CpuQuotaCase(
        name="v2_fractional_rounds_up",
        files={"cpu.max": "150000 100000"},
        expected_assigned=2,
    ),
    CpuQuotaCase(
        name="v1_limited",
        files={"cpu/cpu.cfs_quota_us": "200000", "cpu/cpu.cfs_period_us": "100000"},
        expected_assigned=2,
    ),
    CpuQuotaCase(
        name="v1_unlimited_sentinel",
        files={"cpu/cpu.cfs_quota_us": "-1", "cpu/cpu.cfs_period_us": "100000"},
        expected_assigned=None,
    ),
    CpuQuotaCase(
        name="v1_fractional_rounds_up",
        files={"cpu/cpu.cfs_quota_us": "250000", "cpu/cpu.cfs_period_us": "100000"},
        expected_assigned=3,
    ),
    CpuQuotaCase(
        name="v2_single_core",
        files={"cpu.max": "100000 100000"},
        expected_assigned=1,
    ),
    CpuQuotaCase(
        name="v2_quota_above_host_count",
        files={"cpu.max": "102400000 100000"},
        expected_assigned=1024,
    ),
    CpuQuotaCase(
        name="missing_files",
        files={},
        expected_assigned=None,
    ),
]


def _usable_cores(assigned: int | None) -> int:
    """The host's logical count, capped by the quota and by this test process's real CPU affinity.

    Mirrors the production cap exactly (including the real, ambient affinity reading) so these
    fixture-driven cases hold whether or not the machine running them enforces a cpuset restriction.
    """
    host_count = psutil.cpu_count(logical=True)
    assert host_count is not None
    try:
        affinity_count: int | None = len(psutil.Process().cpu_affinity())
    except (AttributeError, psutil.Error):
        affinity_count = None
    candidates = [value for value in (host_count, assigned, affinity_count) if value is not None]
    return min(candidates)


@pytest.mark.parametrize("case", CPU_QUOTA_CASES, ids=[case.name for case in CPU_QUOTA_CASES])
def test_cgroup_cpu_quota(case: CpuQuotaCase, tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, case.files)

    reading = ProcessResources(cgroup_root=tmp_path).read()

    assert reading.processor_assigned == case.expected_assigned


@pytest.mark.parametrize("case", CPU_QUOTA_CASES, ids=[case.name for case in CPU_QUOTA_CASES])
def test_processor_available_is_the_host_count_capped_by_the_quota(case: CpuQuotaCase, tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, case.files)

    reading = ProcessResources(cgroup_root=tmp_path).read()

    assert reading.processor_available == _usable_cores(case.expected_assigned)


@dataclass
class UsableProcessorsCase:
    name: str
    host_count: int | None
    quota_cores: int | None
    affinity_count: int | None
    expected: int | None


USABLE_PROCESSORS_CASES = [
    UsableProcessorsCase(
        name="affinity_narrower_than_host_and_quota",
        host_count=18,
        quota_cores=None,
        affinity_count=2,
        expected=2,
    ),
    UsableProcessorsCase(
        name="quota_narrower_than_affinity",
        host_count=18,
        quota_cores=4,
        affinity_count=8,
        expected=4,
    ),
    UsableProcessorsCase(
        name="affinity_unreadable_falls_back_to_quota",
        host_count=18,
        quota_cores=4,
        affinity_count=None,
        expected=4,
    ),
    UsableProcessorsCase(
        name="nothing_restricts_reports_the_host_count",
        host_count=18,
        quota_cores=None,
        affinity_count=None,
        expected=18,
    ),
    UsableProcessorsCase(
        name="only_affinity_known",
        host_count=None,
        quota_cores=None,
        affinity_count=3,
        expected=3,
    ),
    UsableProcessorsCase(
        name="nothing_known",
        host_count=None,
        quota_cores=None,
        affinity_count=None,
        expected=None,
    ),
]


@pytest.mark.parametrize("case", USABLE_PROCESSORS_CASES, ids=[case.name for case in USABLE_PROCESSORS_CASES])
def test_usable_processors_caps_by_the_tightest_known_limit(case: UsableProcessorsCase) -> None:
    result = _usable_processors(
        host_count=case.host_count, quota_cores=case.quota_cores, affinity_count=case.affinity_count
    )

    assert result == case.expected


def test_single_core_quota_reports_one_usable_processor(tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, {"cpu.max": "100000 100000"})

    reading = ProcessResources(cgroup_root=tmp_path).read()

    assert reading.processor_available == 1
    assert reading.processor_assigned == 1


@dataclass
class MemoryCase:
    name: str
    files: dict[str, str]
    expected_total: int | None
    expected_available: int | None
    total_from_host: bool = field(default=False)


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
        name="v2_unlimited_falls_back_to_host",
        files={"memory.max": "max"},
        expected_total=None,
        expected_available=None,
        total_from_host=True,
    ),
    MemoryCase(
        name="v1_unlimited_sentinel_falls_back_to_host",
        files={"memory/memory.limit_in_bytes": "9223372036854771712"},
        expected_total=None,
        expected_available=None,
        total_from_host=True,
    ),
    MemoryCase(
        name="missing_files_fall_back_to_host",
        files={},
        expected_total=None,
        expected_available=None,
        total_from_host=True,
    ),
]


@pytest.mark.parametrize("case", MEMORY_CASES, ids=[case.name for case in MEMORY_CASES])
def test_cgroup_memory(case: MemoryCase, tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, case.files)

    reading = ProcessResources(cgroup_root=tmp_path).read()

    if case.total_from_host:
        # A host without a memory limit reports its whole capacity; that value is
        # never ``None`` on a normal host, and free memory is always readable.
        assert reading.memory_total == psutil.virtual_memory().total
        assert reading.memory_available is not None
        assert reading.memory_available >= 0
    else:
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
    expected_memory_total: int | None
    expected_memory_available: int | None


CGROUP_PATH_CASES = [
    CgroupPathCase(
        name="private_namespace_reads_the_root",
        proc_content="0::/\n",
        files={
            "cpu.max": "400000 100000",
            "memory.max": "8589934592",
            "memory.current": "1073741824",
        },
        expected_assigned=4,
        expected_memory_total=8589934592,
        expected_memory_available=8589934592 - 1073741824,
    ),
    CgroupPathCase(
        name="host_namespace_reads_the_process_cgroup",
        proc_content="0::/system.slice/app.scope\n",
        files={
            "system.slice/app.scope/cpu.max": "400000 100000",
            "system.slice/app.scope/memory.max": "8589934592",
            "system.slice/app.scope/memory.current": "1073741824",
        },
        expected_assigned=4,
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
        expected_memory_total=4294967296,
        expected_memory_available=4294967296 - 1073741824,
    ),
    CgroupPathCase(
        name="unresolvable_cgroup_path_falls_back_to_the_root",
        proc_content="0::/vanished.scope\n",
        files={
            "cpu.max": "400000 100000",
            "memory.max": "8589934592",
            "memory.current": "1073741824",
        },
        expected_assigned=4,
        expected_memory_total=8589934592,
        expected_memory_available=8589934592 - 1073741824,
    ),
    CgroupPathCase(
        name="v1_only_proc_file_reads_the_root_controllers",
        proc_content="12:memory:/docker/abc\n3:cpu,cpuacct:/docker/abc\n",
        files={
            "cpu/cpu.cfs_quota_us": "200000",
            "cpu/cpu.cfs_period_us": "100000",
            "memory/memory.limit_in_bytes": "8589934592",
            "memory/memory.usage_in_bytes": "2147483648",
        },
        expected_assigned=2,
        expected_memory_total=8589934592,
        expected_memory_available=8589934592 - 2147483648,
    ),
]


def _process_resources_for(case: CgroupPathCase, tmp_path: Path) -> ProcessResources:
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    _write_cgroup_files(cgroup_root, case.files)
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text(case.proc_content)
    return ProcessResources(cgroup_root=cgroup_root, proc_cgroup=proc_cgroup)


@pytest.mark.parametrize("case", CGROUP_PATH_CASES, ids=[case.name for case in CGROUP_PATH_CASES])
def test_cgroup_path_resolution_cpu(case: CgroupPathCase, tmp_path: Path) -> None:
    reading = _process_resources_for(case, tmp_path).read()

    assert reading.processor_assigned == case.expected_assigned
    assert reading.processor_available == _usable_cores(case.expected_assigned)


@pytest.mark.parametrize("case", CGROUP_PATH_CASES, ids=[case.name for case in CGROUP_PATH_CASES])
def test_cgroup_path_resolution_memory(case: CgroupPathCase, tmp_path: Path) -> None:
    reading = _process_resources_for(case, tmp_path).read()

    assert reading.memory_total == case.expected_memory_total
    assert reading.memory_available == case.expected_memory_available


def test_unlimited_at_every_level_falls_back_to_host(tmp_path: Path) -> None:
    case = CgroupPathCase(
        name="unlimited_everywhere",
        proc_content="0::/a/b\n",
        files={
            "a/b/cpu.max": "max 100000",
            "a/b/memory.max": "max",
            "a/cpu.max": "max 100000",
            "a/memory.max": "max",
        },
        expected_assigned=None,
        expected_memory_total=None,
        expected_memory_available=None,
    )

    reading = _process_resources_for(case, tmp_path).read()

    assert reading.processor_assigned is None
    assert reading.memory_total == psutil.virtual_memory().total
    assert reading.memory_available is not None
    assert reading.memory_available >= 0


def test_binding_ancestor_usage_refreshes_between_reads(tmp_path: Path) -> None:
    # Free memory must be recomputed against the level that holds the effective
    # limit — here the parent — not against the unlimited leaf.
    case = CgroupPathCase(
        name="refresh",
        proc_content="0::/a/b\n",
        files={
            "a/b/memory.max": "max",
            "a/memory.max": "4294967296",
            "a/memory.current": "1073741824",
        },
        expected_assigned=None,
        expected_memory_total=4294967296,
        expected_memory_available=4294967296 - 1073741824,
    )
    reader = _process_resources_for(case, tmp_path)

    first = reader.read()
    assert first.memory_available == 4294967296 - 1073741824

    (tmp_path / "cgroup" / "a" / "memory.current").write_text("2147483648")
    second = reader.read()

    assert second.memory_total == 4294967296
    assert second.memory_available == 4294967296 - 2147483648


def test_host_identifier_is_populated(tmp_path: Path) -> None:
    reading = ProcessResources(cgroup_root=tmp_path).read()

    assert reading.host == socket.gethostname()


def test_limit_values_refresh_between_reads(tmp_path: Path) -> None:
    # A live reconfiguration (a ``docker update --cpus``, a Kubernetes in-place
    # pod resize) rewrites the cgroup limit files without restarting the process,
    # so the CPU quota and memory capacity must reflect it on the next read
    # rather than staying at whatever was true when the process started.
    _write_cgroup_files(
        tmp_path,
        {"cpu.max": "100000 100000", "memory.max": "8589934592", "memory.current": "1073741824"},
    )
    reader = ProcessResources(cgroup_root=tmp_path)

    first = reader.read()
    assert first.processor_assigned == 1
    assert first.memory_total == 8589934592
    assert first.memory_available == 8589934592 - 1073741824

    (tmp_path / "cpu.max").write_text("400000 100000")
    (tmp_path / "memory.max").write_text("4294967296")
    (tmp_path / "memory.current").write_text("536870912")
    second = reader.read()

    assert second.processor_assigned == 4
    assert second.processor_available == _usable_cores(4)
    assert second.memory_total == 4294967296
    assert second.memory_available == 4294967296 - 536870912


def test_cgroup_path_resolution_is_cached_after_first_read(tmp_path: Path) -> None:
    # Resolving the process's own cgroup walks /proc/self/cgroup and its
    # ancestors, and that path cannot move without a container restart, so it
    # must not be re-resolved on every read the way the limit values are.
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    _write_cgroup_files(cgroup_root, {"a/cpu.max": "100000 100000"})
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text("0::/a\n")
    reader = ProcessResources(cgroup_root=cgroup_root, proc_cgroup=proc_cgroup)

    first = reader.read()
    assert first.processor_assigned == 1

    proc_cgroup.unlink()
    second = reader.read()

    assert second.processor_assigned == 1


def test_diagnostics_report_the_enforced_memory_limit(tmp_path: Path) -> None:
    # The limit is what distinguishes an allocation from host capacity, so it is
    # reported directly rather than inferred by comparing the two figures — a
    # limit set to exactly the host's capacity is still a limit.
    _write_cgroup_files(tmp_path, {"memory.max": "8589934592", "memory.current": "1073741824"})

    diagnostics = ProcessResources(cgroup_root=tmp_path).diagnose()

    assert diagnostics.memory_limit == 8589934592
    assert diagnostics.reading.memory_total == 8589934592


def test_diagnostics_report_no_limit_when_memory_is_unbounded(tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, {"memory.max": "max"})

    diagnostics = ProcessResources(cgroup_root=tmp_path).diagnose()

    assert diagnostics.memory_limit is None
    assert diagnostics.reading.memory_total == psutil.virtual_memory().total


def test_diagnostics_expose_the_limit_files_found_at_each_level(tmp_path: Path) -> None:
    case = CgroupPathCase(
        name="ancestor",
        proc_content="0::/a/b\n",
        files={
            "a/b/memory.max": "max",
            "a/memory.max": "4294967296",
            "a/memory.current": "1073741824",
        },
        expected_assigned=None,
        expected_memory_total=4294967296,
        expected_memory_available=4294967296 - 1073741824,
    )
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    _write_cgroup_files(cgroup_root, case.files)
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text(case.proc_content)

    diagnostics = ProcessResources(cgroup_root=cgroup_root, proc_cgroup=proc_cgroup).diagnose()

    assert [level.path for level in diagnostics.levels] == [
        str(cgroup_root / "a" / "b"),
        str(cgroup_root / "a"),
        str(cgroup_root),
    ]
    assert diagnostics.levels[0].files == {"memory.max": "max"}
    assert diagnostics.levels[1].files == {"memory.max": "4294967296", "memory.current": "1073741824"}
    assert diagnostics.levels[2].files == {}
    assert diagnostics.memory_limit == 4294967296


def test_leaf_cpu_max_absent_still_falls_through_to_ancestor(tmp_path: Path) -> None:
    """A leaf with no ``cpu.max`` file at all (ENOENT) is the normal per-level case.

    It must keep falling through to an ancestor's limit exactly as before — only a
    genuine read failure (not a missing file) should stop that fallback.
    """
    cgroup_root = tmp_path / "cgroup"
    (cgroup_root / "a" / "b").mkdir(parents=True)  # leaf exists but carries no cpu.max of its own
    (cgroup_root / "a" / "cpu.max").write_text("200000 100000")
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text("0::/a/b\n")

    reading = ProcessResources(cgroup_root=cgroup_root, proc_cgroup=proc_cgroup).read()

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
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    (cgroup_root / "a" / "b").mkdir(parents=True)
    (cgroup_root / "a" / "b" / "cpu.max").mkdir()  # a directory, not a file: read raises IsADirectoryError
    (cgroup_root / "a" / "cpu.max").write_text("200000 100000")
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text("0::/a/b\n")

    with caplog.at_level(logging.WARNING, logger="infrahub.telemetry.resources"):
        reading = ProcessResources(cgroup_root=cgroup_root, proc_cgroup=proc_cgroup).read()

    assert reading.processor_assigned is None
    assert reading.processor_available is None
    warnings = [
        record
        for record in caplog.records
        if "reporting the CPU quota as unknown" in record.message and "cpu.max" in record.message
    ]
    assert len(warnings) == 1


def test_unreadable_memory_max_reports_unknown_instead_of_ancestor_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    (cgroup_root / "a" / "b").mkdir(parents=True)
    (cgroup_root / "a" / "b" / "memory.max").mkdir()
    (cgroup_root / "a" / "memory.max").write_text("4294967296")
    (cgroup_root / "a" / "memory.current").write_text("1073741824")
    proc_cgroup = tmp_path / "proc_self_cgroup"
    proc_cgroup.write_text("0::/a/b\n")

    with caplog.at_level(logging.WARNING, logger="infrahub.telemetry.resources"):
        reading = ProcessResources(cgroup_root=cgroup_root, proc_cgroup=proc_cgroup).read()

    assert reading.memory_total is None
    assert reading.memory_available is None
    warnings = [
        record
        for record in caplog.records
        if "reporting memory as unknown" in record.message and "memory.max" in record.message
    ]
    assert len(warnings) == 1


def test_unreadable_cpu_max_does_not_affect_memory_fields(tmp_path: Path) -> None:
    """CPU and memory are collected independently: a CPU-only failure must not null memory."""
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    (cgroup_root / "cpu.max").mkdir()
    (cgroup_root / "memory.max").write_text("8589934592")
    (cgroup_root / "memory.current").write_text("1073741824")

    reading = ProcessResources(cgroup_root=cgroup_root).read()

    assert reading.processor_assigned is None
    assert reading.processor_available is None
    assert reading.memory_total == 8589934592
    assert reading.memory_available == 8589934592 - 1073741824


def test_unreadable_memory_max_does_not_affect_cpu_fields(tmp_path: Path) -> None:
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir()
    (cgroup_root / "memory.max").mkdir()
    (cgroup_root / "cpu.max").write_text("400000 100000")

    reading = ProcessResources(cgroup_root=cgroup_root).read()

    assert reading.memory_total is None
    assert reading.memory_available is None
    assert reading.processor_assigned == 4
    assert reading.processor_available == _usable_cores(4)

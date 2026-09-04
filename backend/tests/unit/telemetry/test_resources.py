"""Unit tests for the per-process resource reader.

The reader parses the container control group (cgroup v2 first, then v1) for the
enforced CPU quota and the memory limit, and falls back to whole-host figures
from psutil when no control group is present. Every case is driven from fixture
files under a temporary cgroup root, so no host state or patching is needed.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import psutil
import pytest

from infrahub.telemetry.resources import ProcessResources

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
        name="missing_files",
        files={},
        expected_assigned=None,
    ),
]


@pytest.mark.parametrize("case", CPU_QUOTA_CASES, ids=[case.name for case in CPU_QUOTA_CASES])
def test_cgroup_cpu_quota(case: CpuQuotaCase, tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, case.files)

    reading = ProcessResources(cgroup_root=tmp_path).read()

    assert reading.processor_assigned == case.expected_assigned


@pytest.mark.parametrize("case", CPU_QUOTA_CASES, ids=[case.name for case in CPU_QUOTA_CASES])
def test_processor_available_is_always_logical(case: CpuQuotaCase, tmp_path: Path) -> None:
    _write_cgroup_files(tmp_path, case.files)

    reading = ProcessResources(cgroup_root=tmp_path).read()

    assert reading.processor_available == psutil.cpu_count(logical=True)


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


def test_static_fields_are_cached_only_free_memory_refreshes(tmp_path: Path) -> None:
    # A cgroup-limited memory reading recomputes free memory from ``memory.current``
    # on each read, while capacity stays fixed.
    _write_cgroup_files(
        tmp_path,
        {"memory.max": "8589934592", "memory.current": "1073741824"},
    )
    reader = ProcessResources(cgroup_root=tmp_path)

    first = reader.read()
    assert first.memory_total == 8589934592
    assert first.memory_available == 8589934592 - 1073741824

    (tmp_path / "memory.current").write_text("2147483648")
    second = reader.read()

    assert second.memory_total == 8589934592
    assert second.memory_available == 8589934592 - 2147483648

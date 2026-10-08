"""Read how much CPU and memory this process is allowed to use.

Two sources are read:

- The container limit, from the Linux "cgroup" files where Docker or Kubernetes
  writes the limit it puts on a container, for example "2 CPUs and 4 GB".
- The whole machine, from psutil, for example "18 CPUs and 64 GB".

If a container limit is set, the limit is reported, because that is all the
process can use. If no limit is set, the machine's figures are reported,
because the process can then use the whole machine: a laptop, bare metal, a
VM, or a container started without limits. Both sources are needed, because
inside a container psutil still sees the whole machine, and without a limit
the cgroup files have no number to give.

Three rules apply on top of that:

- A limit that is set but cannot be read is reported as unknown (``None``),
  never as the machine's figures, which could be far too high.
- The assigned CPUs come only from the container limit. With no limit they stay
  ``None``; they are never filled in from the machine.
- The usable CPUs are the smallest of the machine's CPU count, the container's
  CPU limit and the number of CPUs the process is pinned to, if it is pinned.

A limit can be set on the container or on a group above it, so every level up
to the top is checked and the tightest limit wins. Limits can change while the
process runs, so they are read again every time.
"""

from __future__ import annotations

import logging
import math
import socket
from dataclasses import dataclass
from pathlib import Path

import psutil
from pydantic import BaseModel, Field

# Standard-library logging, because this module must also work when copied outside the infrahub package.
log = logging.getLogger(__name__)

CGROUP_ROOT = Path("/sys/fs/cgroup")
PROC_SELF_CGROUP = Path("/proc/self/cgroup")
PROC_SELF_PID_NAMESPACE = Path("/proc/self/ns/pid")

# A CPU limit is written as CPU time allowed per period; this is the period used when the file leaves it out.
_DEFAULT_CPU_PERIOD_US = 100000

# The older cgroup format writes a huge number to mean "no memory limit", so anything this large is not a real limit.
_CGROUP_MEMORY_UNLIMITED_THRESHOLD = 2**62

# The errors a read can still raise, all worth retrying, because bad values in the limit files are handled where they are read.
RESOURCE_READ_FAILURES = (OSError, psutil.Error)

# Stored as the container name only when even the name cannot be read, so the reading matches no real container.
UNKNOWN_CONTAINER = "unknown"


class WorkerResourceReading(BaseModel):
    """One process's CPU and memory figures, as stored in the cache between heartbeats.

    ``host`` names the container by its hostname and its process ID namespace, so
    that processes sharing a container can split its figures between them; it is
    never sent. The figures cannot be negative, so a damaged cache entry is rejected
    when it is read back.
    """

    host: str
    processor_available: int | None = Field(default=None, ge=0)
    processor_assigned: int | None = Field(default=None, ge=0)
    memory_total: int | None = Field(default=None, ge=0)
    memory_available: int | None = Field(default=None, ge=0)

    @classmethod
    def failed(cls, *, host: str) -> WorkerResourceReading:
        """The reading stored when a process could not read its figures at all: no figures, but still its container's name."""
        return cls(host=host)

    @property
    def is_failed(self) -> bool:
        """Whether every figure is missing, which only happens when the whole read failed."""
        return all(value is None for value in self.model_dump(exclude={"host"}).values())


@dataclass(frozen=True)
class _ProcessIdentity:
    """Facts about the process that only change when its container restarts."""

    host: str
    cgroup_dirs: list[Path]
    host_processor_count: int | None

    v1_cpu_dirs: list[Path]
    """Where the older cgroup format keeps this process's CPU limits, nearest level first; empty otherwise."""

    v1_memory_dirs: list[Path]
    """Where the older cgroup format keeps this process's memory limits, nearest level first; empty otherwise."""


def _read_text_file(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except (OSError, ValueError):
        return None


def _read_int_file(path: Path) -> int | None:
    content = _read_text_file(path)
    if content is None:
        return None
    try:
        return int(content)
    except ValueError:
        return None


class _CgroupLimitUnusableError(Exception):
    """A limit file exists, but its limit cannot be read or understood, so the limit is unknown.

    This is different from a missing file, which means no limit is set at that level.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path: Path = path


class _CgroupUsageUnreadableError(Exception):
    """A memory usage file could not be read, so the free memory under that limit is unknown."""

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path: Path = path


def _read_cgroup_limit_file(path: Path) -> str | None:
    """Read one limit file, or return ``None`` when it is missing, which means no limit at this level.

    A file that exists but cannot be read is never treated as missing, because a
    looser limit higher up would then win.

    Raises:
        _CgroupLimitUnusableError: The file exists but could not be read.

    """
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise _CgroupLimitUnusableError(path) from exc


def _read_cgroup_int_limit(path: Path) -> int | None:
    """Read one whole-number limit, or return ``None`` when the file is missing.

    Raises:
        _CgroupLimitUnusableError: The file holds something other than a number, so the limit is unknown.

    """
    content = _read_cgroup_limit_file(path)
    if content is None:
        return None
    try:
        return int(content)
    except ValueError as exc:
        raise _CgroupLimitUnusableError(path) from exc


def _quota_to_cores(quota: int, period: int) -> float | None:
    """Turn a CPU limit, written as CPU time allowed per period, into a number of CPUs.

    The fraction is kept because the assigned and usable CPU figures round it in
    opposite directions. A zero or negative value means no limit.
    """
    if quota <= 0 or period <= 0:
        return None
    return quota / period


def _enforced_cores(quota_cores: float | None) -> int | None:
    """The assigned CPUs: the limit rounded up, so the figure never understates what the container is allowed."""
    return None if quota_cores is None else math.ceil(quota_cores)


def _usable_cores_under_quota(quota_cores: float | None) -> int | None:
    """The CPUs a limit lets the process keep busy: the limit rounded down, but never below one.

    A limit of 2.5 CPUs cannot keep a third CPU fully busy, so it counts as 2. A
    limit below one CPU still gives the process some CPU, so it counts as 1.
    """
    return None if quota_cores is None else max(1, math.floor(quota_cores))


def _usable_processors(host_count: int | None, quota_cores: int | None, affinity_count: int | None) -> int | None:
    """The usable CPUs: the smallest of the machine's CPU count, the CPU limit and the CPUs the process is pinned to.

    A figure that is not known (``None``: no limit set, or pinning unreadable) is
    skipped. The result is ``None`` only when none of the three is known.
    """
    knowns = [value for value in (host_count, quota_cores, affinity_count) if value is not None]
    return min(knowns) if knowns else None


def _affinity_processor_count() -> int | None:
    """How many CPUs this process is pinned to, or ``None`` when that cannot be read.

    A container can be pinned to specific CPUs without a CPU limit (for example
    ``docker run --cpuset-cpus``), which the limit alone would miss. On platforms
    that do not support pinning, psutil raises ``NotImplementedError``, which is
    treated as unknown rather than failing the whole read.
    """
    try:
        return len(psutil.Process().cpu_affinity())
    except (AttributeError, NotImplementedError, OSError, psutil.Error):
        return None


def _own_cgroup_dirs(cgroup_root: Path, proc_cgroup: Path) -> list[Path]:
    """Return the folders that can hold this process's limits, from its own level up to the top.

    In most containers the process only sees its own level, so this is just the
    top folder. Elsewhere (some older container setups, or a service run directly
    on a Linux machine) the process's place in the tree is read from
    ``/proc/self/cgroup`` and every level above it is included, because a limit
    can be set on any of them. Anything unexpected falls back to the top folder.
    """
    content = _read_text_file(proc_cgroup)
    if content is None:
        return [cgroup_root]
    for line in content.splitlines():
        if not line.startswith("0::"):
            continue
        relative = line[3:].strip().lstrip("/")
        if not relative or ".." in relative.split("/"):
            return [cgroup_root]
        leaf = cgroup_root / relative
        if not leaf.is_dir():
            return [cgroup_root]
        dirs = [leaf]
        for parent in leaf.parents:
            dirs.append(parent)
            if parent == cgroup_root:
                break
        return dirs
    return [cgroup_root]


def _v1_controller_mount(cgroup_root: Path, controller: str) -> Path | None:
    """Where the older cgroup format keeps one kind of limit, such as ``cpu`` or ``memory``.

    It often shares a folder with a related kind, so ``cpu`` may live in ``cpu,cpuacct``.
    """
    direct = cgroup_root / controller
    if direct.is_dir():
        return direct
    try:
        entries = sorted(cgroup_root.iterdir())
    except OSError:
        return None
    return next((entry for entry in entries if entry.is_dir() and controller in entry.name.split(",")), None)


def _v1_controller_dirs(cgroup_root: Path, proc_cgroup: Path, controller: str) -> list[Path]:
    """Return this process's folders for one kind of limit in the older cgroup format, nearest level first.

    The older format keeps each kind of limit in its own tree, and
    ``/proc/self/cgroup`` lists the process's place in each tree separately.
    """
    mount = _v1_controller_mount(cgroup_root, controller)
    if mount is None:
        return []
    content = _read_text_file(proc_cgroup)
    if content is None:
        return [mount]
    for line in content.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or controller not in fields[1].split(","):
            continue
        relative = fields[2].strip().lstrip("/")
        if not relative or ".." in relative.split("/"):
            return [mount]
        leaf = mount / relative
        if not leaf.is_dir():
            return [mount]
        dirs = [leaf]
        for parent in leaf.parents:
            dirs.append(parent)
            if parent == mount:
                break
        return dirs
    return [mount]


def _parse_cpu_max(line: str, path: Path) -> float | None:
    """Read one CPU limit line: "<CPU time allowed> <period>", or "max" for no limit.

    Raises:
        _CgroupLimitUnusableError: The line is neither, so the limit is unknown.

    """
    parts = line.split()
    if not parts:
        raise _CgroupLimitUnusableError(path)
    if parts[0] == "max":
        return None
    try:
        quota = int(parts[0])
        period = int(parts[1]) if len(parts) > 1 else _DEFAULT_CPU_PERIOD_US
    except ValueError as exc:
        raise _CgroupLimitUnusableError(path) from exc
    return _quota_to_cores(quota=quota, period=period)


def _read_cgroup_cpu_quota(cgroup_dirs: list[Path], v1_dirs: list[Path]) -> float | None:
    """Return the CPU limit as a number of CPUs, fraction kept, or ``None`` when no limit is set.

    A limit can be set at any level, so the tightest one wins. The current file
    format is read first; if no level has it, the older format is read.

    Raises:
        _CgroupLimitUnusableError: A limit file exists but cannot be used. The limit
            is then unknown; skipping it would let a looser limit higher up win.

    """
    v2_cores: list[float] = []
    v2_seen = False
    for directory in cgroup_dirs:
        path = directory / "cpu.max"
        line = _read_cgroup_limit_file(path)
        if line is None:
            continue
        v2_seen = True
        if (level_cores := _parse_cpu_max(line, path)) is not None:
            v2_cores.append(level_cores)
    if v2_seen:
        return min(v2_cores) if v2_cores else None

    quotas = []
    for directory in v1_dirs:
        quota = _read_cgroup_int_limit(directory / "cpu.cfs_quota_us")
        period = _read_cgroup_int_limit(directory / "cpu.cfs_period_us")
        if quota is None or period is None:
            continue
        if (level_cores := _quota_to_cores(quota=quota, period=period)) is not None:
            quotas.append(level_cores)
    return min(quotas) if quotas else None


def _read_cgroup_memory_levels(cgroup_dirs: list[Path], v1_dirs: list[Path]) -> list[tuple[int, Path]]:
    """Return every memory limit that is set, each with the file showing the memory used under it.

    The current file format is read first; if no level has it, the older format
    is read. An empty list means no memory limit is set anywhere.

    Raises:
        _CgroupLimitUnusableError: A limit file exists but cannot be used. The limit
            is then unknown; skipping it would let a looser limit higher up win.

    """
    levels: list[tuple[int, Path]] = []
    v2_seen = False
    for directory in cgroup_dirs:
        raw = _read_cgroup_limit_file(directory / "memory.max")
        if raw is None:
            continue
        v2_seen = True
        if raw == "max":
            continue
        try:
            limit = int(raw)
        except ValueError as exc:
            raise _CgroupLimitUnusableError(directory / "memory.max") from exc
        levels.append((limit, directory / "memory.current"))
    if v2_seen:
        return levels

    for directory in v1_dirs:
        v1_limit = _read_cgroup_int_limit(directory / "memory.limit_in_bytes")
        if v1_limit is None or v1_limit >= _CGROUP_MEMORY_UNLIMITED_THRESHOLD:
            continue
        levels.append((v1_limit, directory / "memory.usage_in_bytes"))
    return levels


def _memory_headroom(levels: list[tuple[int, Path]]) -> int:
    """The free memory: the smallest amount left under any of the limits.

    A limit set higher up also counts the memory used by everything below it, so
    a nearly full level higher up can leave less room than the container's own
    limit suggests. A limit that is already exceeded counts as zero free, never
    as a negative amount.

    Raises:
        _CgroupUsageUnreadableError: A usage file could not be read, so the free memory is unknown.

    """
    headroom = []
    for limit, usage_path in levels:
        current = _read_int_file(usage_path)
        if current is None:
            raise _CgroupUsageUnreadableError(usage_path)
        headroom.append(max(0, limit - current))
    return min(headroom)


def _host_memory_total() -> int | None:
    return int(psutil.virtual_memory().total)


def _host_memory_available() -> int | None:
    return int(psutil.virtual_memory().available)


class ProcessResources:
    """Read this process's CPU and memory figures.

    The container name, where the limit files are and the machine's CPU count only
    change when the container restarts, so they are read once. The limits and the
    free memory can change while the process runs, so they are read every time.
    """

    def __init__(
        self,
        cgroup_root: Path = CGROUP_ROOT,
        proc_cgroup: Path = PROC_SELF_CGROUP,
        pid_namespace: Path = PROC_SELF_PID_NAMESPACE,
    ) -> None:
        self._cgroup_root = cgroup_root
        self._proc_cgroup = proc_cgroup
        self._pid_namespace = pid_namespace
        self._identity: _ProcessIdentity | None = None

    def container_name(self) -> str:
        """The name of the container this process runs in, the same for every process in that container.

        The hostname alone is not enough, because separate containers can share one,
        for example when they use the host's network. Linux gives each container its
        own process ID namespace, shared by every process inside it, so the name is
        the hostname followed by that namespace, such as ``api-1/pid:[4026532001]``.
        Where the namespace cannot be read, for example outside Linux, the name is the
        hostname alone.

        Raises:
            OSError: The hostname could not be read.

        """
        hostname = socket.gethostname()
        try:
            namespace = self._pid_namespace.readlink()
        except OSError:
            return hostname
        return f"{hostname}/{namespace}"

    def _read_identity(self) -> _ProcessIdentity:
        return _ProcessIdentity(
            host=self.container_name(),
            cgroup_dirs=_own_cgroup_dirs(cgroup_root=self._cgroup_root, proc_cgroup=self._proc_cgroup),
            host_processor_count=psutil.cpu_count(logical=True),
            v1_cpu_dirs=_v1_controller_dirs(self._cgroup_root, self._proc_cgroup, "cpu"),
            v1_memory_dirs=_v1_controller_dirs(self._cgroup_root, self._proc_cgroup, "memory"),
        )

    def _process_identity(self) -> _ProcessIdentity:
        if self._identity is None:
            self._identity = self._read_identity()
        return self._identity

    def read(self) -> WorkerResourceReading:
        identity = self._process_identity()
        try:
            quota_cores = _read_cgroup_cpu_quota(identity.cgroup_dirs, identity.v1_cpu_dirs)
            processor_assigned = _enforced_cores(quota_cores)
            processor_available = _usable_processors(
                host_count=identity.host_processor_count,
                quota_cores=_usable_cores_under_quota(quota_cores),
                affinity_count=_affinity_processor_count(),
            )
        except _CgroupLimitUnusableError as exc:
            # The unreadable limit could be the tightest one, and the machine's figures could be far too high.
            log.warning(
                "CPU limit file %s exists but could not be used; reporting the CPU figures as unknown (host=%s)",
                exc.path,
                identity.host,
            )
            processor_assigned = None
            processor_available = None

        try:
            memory_levels = _read_cgroup_memory_levels(identity.cgroup_dirs, identity.v1_memory_dirs)
            memory_limit = min(limit for limit, _ in memory_levels) if memory_levels else None
            memory_total = memory_limit if memory_limit is not None else _host_memory_total()
        except _CgroupLimitUnusableError as exc:
            log.warning(
                "Memory limit file %s exists but could not be used; reporting memory as unknown (host=%s)",
                exc.path,
                identity.host,
            )
            return WorkerResourceReading(
                host=identity.host,
                processor_available=processor_available,
                processor_assigned=processor_assigned,
            )
        except RESOURCE_READ_FAILURES as exc:
            # No memory limit is set, so this failure came from reading the machine's memory, not a limit file.
            log.warning(
                "Host memory capacity read failed; reporting memory as unknown (host=%s): %s",
                identity.host,
                exc,
            )
            return WorkerResourceReading(
                host=identity.host,
                processor_available=processor_available,
                processor_assigned=processor_assigned,
            )

        # Free memory is read on its own, so failing to read it does not lose the total.
        try:
            memory_available = _memory_headroom(memory_levels) if memory_levels else _host_memory_available()
        except _CgroupUsageUnreadableError as exc:
            log.warning(
                "Memory usage file %s could not be read; reporting free memory as unknown (host=%s)",
                exc.path,
                identity.host,
            )
            memory_available = None
        except RESOURCE_READ_FAILURES as exc:
            log.warning(
                "Host free-memory read failed; reporting free memory as unknown (host=%s): %s",
                identity.host,
                exc,
            )
            memory_available = None

        return WorkerResourceReading(
            host=identity.host,
            processor_available=processor_available,
            processor_assigned=processor_assigned,
            memory_total=memory_total,
            memory_available=memory_available,
        )

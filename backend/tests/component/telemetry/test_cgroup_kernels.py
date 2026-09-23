"""Exercise the per-process resource reader against real kernel control groups.

The unit tests drive fixture files under a temporary root, which pins the parsing
but not the layout: a container runtime decides where the process's control group
sits and whether the limit files are visible at the apparent root at all. These
cases run the reader inside containers configured for each layout that occurs in
practice — a private cgroup namespace, a host namespace, and a limit enforced on
an ancestor rather than on the process's own group — so a regression in the path
resolution fails here rather than in a deployment.

Requires a Docker daemon and a Linux kernel with cgroup v2, plus network access
the first time — the probe image pulls a base image and installs into it. Every
docker call is bounded, so a stalled daemon or registry fails the run rather
than hanging it. cgroup v1 layouts are
covered by the unit fixtures; no current runner exposes a v1 hierarchy.

Also requires network access: the probe image build pulls a base image and installs
its packages, so this suite cannot run fully offline.
"""

from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404
from dataclasses import dataclass
from pathlib import Path

import pytest

RESOURCES_MODULE = Path(__file__).parents[3] / "infrahub" / "telemetry" / "resources.py"
DOCKER = shutil.which("docker")

_MEBIBYTE = 1024**2

# A responsive daemon answers at once; a build may pull a base image and install into
# it; a probe run is a few file reads. Bounded so a stall fails rather than hangs.
_DAEMON_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 600
_RUN_TIMEOUT_SECONDS = 120

# Import the module straight from a bind mount rather than through the ``infrahub``
# package, whose import needs distribution metadata that a bare image lacks.
_PROBE = """
import json, sys
sys.path.insert(0, "/mounted")
import psutil, resources
reading = resources.ProcessResources().read()
print(json.dumps(reading.model_dump() | {
    "host_memory_total": psutil.virtual_memory().total,
    "host_processor_available": psutil.cpu_count(logical=True),
    "affinity_available": len(psutil.Process().cpu_affinity()),
}))
"""

# Enforce the limits on the parent and leave the process's own group unbounded,
# the shape a pod-level limit produces. The parent must be vacated before its
# controllers can be delegated to children.
#
# This runs privileged against the host's cgroup hierarchy, so it refuses to act
# unless it has resolved its own non-root group: an unresolved path would place
# the limits on the root and throttle everything else sharing the machine.
_ANCESTOR_LIMIT_SETUP = """
set -e
own=$(sed -n 's/^0:://p' /proc/self/cgroup)
if [ -z "$own" ] || [ "$own" = "/" ]; then
    echo "refusing to run: own cgroup did not resolve to a non-root path" >&2
    exit 3
fi
cgroup=/sys/fs/cgroup$own
if [ ! -d "$cgroup" ]; then
    echo "refusing to run: $cgroup is not a directory" >&2
    exit 3
fi
mkdir -p $cgroup/leaf
echo $$ > $cgroup/leaf/cgroup.procs
echo '+memory +cpu' > $cgroup/cgroup.subtree_control
echo 536870912 > $cgroup/memory.max
echo '200000 100000' > $cgroup/cpu.max
"""


@dataclass(frozen=True)
class KernelCase:
    name: str

    docker_args: list[str]
    """Flags that put the container in the layout under test."""

    expected_assigned: int | None
    expected_memory_total: int | None
    """Bytes, or ``None`` when the reading should fall back to the whole host."""

    expected_usable: int | None = None
    """Cores the quota lets the process occupy, when a fractional quota makes that differ."""

    expected_affinity: int | None = None
    """CPUs pinned by a ``cpuset`` restriction, applied as a further cap independent of the quota."""

    setup: str = ""


KERNEL_CASES = [
    KernelCase(
        name="private_namespace_reads_container_limits",
        docker_args=["--cpus=1.5", "--memory=512m"],
        expected_assigned=2,
        expected_usable=1,
        expected_memory_total=512 * _MEBIBYTE,
    ),
    KernelCase(
        name="host_namespace_reads_container_limits",
        docker_args=["--cgroupns=host", "--cpus=1.5", "--memory=512m"],
        expected_assigned=2,
        expected_usable=1,
        expected_memory_total=512 * _MEBIBYTE,
    ),
    KernelCase(
        name="ancestor_limit_applies_to_an_unlimited_leaf",
        docker_args=["--cgroupns=host", "--privileged"],
        expected_assigned=2,
        expected_memory_total=512 * _MEBIBYTE,
        setup=_ANCESTOR_LIMIT_SETUP,
    ),
    KernelCase(
        name="whole_core_quota_is_not_rounded",
        docker_args=["--cpus=4", "--memory=1g"],
        expected_assigned=4,
        expected_memory_total=1024 * _MEBIBYTE,
    ),
    KernelCase(
        name="no_limits_report_the_whole_host",
        docker_args=[],
        expected_assigned=None,
        expected_memory_total=None,
    ),
    KernelCase(
        name="cpuset_without_quota_caps_available_by_affinity",
        docker_args=["--cpuset-cpus=0-1"],
        expected_assigned=None,
        expected_memory_total=None,
        expected_affinity=2,
    ),
]


def _docker_on_cgroup_v2() -> bool:
    """Whether a reachable daemon runs containers on a unified cgroup hierarchy.

    The daemon is asked rather than this machine, since it may sit in a VM (the
    macOS case) or on another host, and it is the daemon's hierarchy the cases
    write limits into. On a v1 daemon the setup script finds no unified line and
    refuses, so the cases must skip rather than fail.
    """
    if DOCKER is None:
        return False
    try:
        completed = subprocess.run(  # noqa: S603
            [DOCKER, "info", "--format", "{{.CgroupVersion}}"],
            capture_output=True,
            check=False,
            timeout=_DAEMON_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0 and completed.stdout.decode(errors="replace").strip() == "2"


pytestmark = pytest.mark.skipif(
    not _docker_on_cgroup_v2(), reason="requires a running Docker daemon on a cgroup v2 host"
)


@pytest.fixture(scope="module")
def probe_image() -> str:
    """Build a minimal image carrying only the reader's runtime dependencies."""
    tag = "infrahub-cgroup-probe:test"
    dockerfile = "FROM python:3.12-slim\nRUN pip install --no-cache-dir psutil pydantic\n"
    try:
        subprocess.run(  # noqa: S603
            [DOCKER, "build", "--quiet", "--tag", tag, "-"],
            input=dockerfile.encode(),
            capture_output=True,
            check=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        # The build pulls a base image and installs into it, so a runner without
        # registry access cannot produce the probe. That is a missing prerequisite
        # rather than a regression in the reader.
        pytest.skip(f"probe image could not be built: {exc.stderr.decode(errors='replace').strip()[-300:]}")
    except subprocess.TimeoutExpired:
        pytest.skip("probe image build timed out")
    return tag


@pytest.mark.parametrize("case", KERNEL_CASES, ids=[case.name for case in KERNEL_CASES])
def test_reader_against_real_cgroups(case: KernelCase, probe_image: str) -> None:
    command = [
        DOCKER,
        "run",
        "--rm",
        *case.docker_args,
        "--volume",
        f"{RESOURCES_MODULE}:/mounted/resources.py:ro",
        probe_image,
        "sh",
        "-c",
        f"{case.setup}\npython -c '{_PROBE}'",
    ]
    result = subprocess.run(  # noqa: S603
        command, capture_output=True, text=True, check=False, timeout=_RUN_TIMEOUT_SECONDS
    )
    if result.returncode != 0 and "cpuset" in result.stderr.lower():
        # The case pins specific CPU ids, which a daemon confined to a different set
        # refuses before the reader ever runs.
        pytest.skip(f"the daemon does not allow this CPU set: {result.stderr.strip()[-200:]}")
    assert result.returncode == 0, f"container failed: {result.stderr}"

    reading = json.loads(result.stdout.strip().splitlines()[-1])

    # 'available' is what the process can use: the host's count capped by the quota (rounded
    # down, since a fraction of a core cannot keep a whole one busy) and by CPU affinity,
    # while 'assigned' rounds the same quota up to the cap that is enforced.
    host_count = reading["host_processor_available"]
    quota_cap = case.expected_usable if case.expected_usable is not None else case.expected_assigned
    expected_available = host_count if quota_cap is None else min(host_count, quota_cap)
    if case.expected_affinity is not None:
        assert reading["affinity_available"] == case.expected_affinity
        expected_available = min(expected_available, case.expected_affinity)
    assert reading["processor_available"] == expected_available
    assert reading["processor_available"] >= 1

    assert reading["processor_assigned"] == case.expected_assigned
    assert reading["memory_available"] is not None
    if case.expected_memory_total is None:
        assert reading["memory_total"] == reading["host_memory_total"]
        assert reading["memory_available"] >= 0
    else:
        assert reading["memory_total"] == case.expected_memory_total
        assert 0 <= reading["memory_available"] <= case.expected_memory_total

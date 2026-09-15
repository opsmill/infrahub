"""Exercise the per-process resource reader against real kernel control groups.

The unit tests drive fixture files under a temporary root, which pins the parsing
but not the layout: a container runtime decides where the process's control group
sits and whether the limit files are visible at the apparent root at all. These
cases run the reader inside containers configured for each layout that occurs in
practice — a private cgroup namespace, a host namespace, and a limit enforced on
an ancestor rather than on the process's own group — so a regression in the path
resolution fails here rather than in a deployment.

Requires a Docker daemon and a Linux kernel with cgroup v2. cgroup v1 layouts are
covered by the unit fixtures; no current runner exposes a v1 hierarchy.
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

    setup: str = ""


KERNEL_CASES = [
    KernelCase(
        name="private_namespace_reads_container_limits",
        docker_args=["--cpus=1.5", "--memory=512m"],
        expected_assigned=2,
        expected_memory_total=512 * _MEBIBYTE,
    ),
    KernelCase(
        name="host_namespace_reads_container_limits",
        docker_args=["--cgroupns=host", "--cpus=1.5", "--memory=512m"],
        expected_assigned=2,
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
]


def _docker_available() -> bool:
    if DOCKER is None:
        return False
    return subprocess.run([DOCKER, "info"], capture_output=True, check=False).returncode == 0  # noqa: S603


pytestmark = pytest.mark.skipif(not _docker_available(), reason="requires a running Docker daemon")


@pytest.fixture(scope="module")
def probe_image() -> str:
    """Build a minimal image carrying only the reader's runtime dependencies."""
    tag = "infrahub-cgroup-probe:test"
    dockerfile = "FROM python:3.12-slim\nRUN pip install --no-cache-dir psutil pydantic\n"
    subprocess.run(  # noqa: S603
        [DOCKER, "build", "--quiet", "--tag", tag, "-"],
        input=dockerfile.encode(),
        capture_output=True,
        check=True,
    )
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
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    assert result.returncode == 0, f"container failed: {result.stderr}"

    reading = json.loads(result.stdout.strip().splitlines()[-1])

    # A CPU quota never narrows the reported core count: 'available' is what the host
    # has, 'assigned' is what is enforced, and the audit needs both separately.
    assert reading["processor_available"] == reading["host_processor_available"]
    assert reading["processor_available"] >= 1

    assert reading["processor_assigned"] == case.expected_assigned
    if case.expected_memory_total is None:
        assert reading["memory_total"] == reading["host_memory_total"]
    else:
        assert reading["memory_total"] == case.expected_memory_total
    assert reading["memory_available"] is not None
    assert reading["memory_available"] >= 0

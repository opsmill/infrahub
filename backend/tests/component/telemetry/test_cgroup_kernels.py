"""Exercise the per-process resource reader against real kernel control groups.

The unit tests drive fixture files under a temporary root, which pins the parsing
but not the layout: a container runtime decides where the process's control group
sits and whether the limit files are visible at the apparent root at all. These
cases run the reader inside containers configured for each layout that occurs in
practice — a private cgroup namespace, a host namespace, and a limit enforced on
an ancestor rather than on the process's own group — so a regression in the path
resolution fails here rather than in a deployment. They also check that the name
the reader gives its container is the hostname plus the container's process ID namespace.

Requires a Docker daemon on a Linux kernel with cgroup v2, and network access the
first time, since the probe image pulls a Python base image and installs the
reader's dependencies into it. Every Docker call is bounded, so a stalled daemon
or registry fails the run rather than hanging it. cgroup v1 layouts are covered by
the unit fixtures; no current runner exposes a v1 hierarchy.
"""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from docker.errors import APIError, BuildError, DockerException
from requests.exceptions import RequestException
from testcontainers.core.container import DockerContainer
from testcontainers.core.docker_client import DockerClient
from testcontainers.core.image import DockerImage

RESOURCES_MODULE = Path(__file__).parents[3] / "infrahub" / "telemetry" / "resources.py"

_MEBIBYTE = 1024**2
_NANO_CPUS_PER_CPU = 10**9
# The kernel takes a CPU limit as microseconds of CPU time per period, so N CPUs is N times this period.
_CPU_PERIOD_US = 100_000

_MEMORY_LIMIT = 512 * _MEBIBYTE
_WHOLE_CPU_LIMIT = 2
# A fraction makes the assigned figure round up and the usable one round down, so the two can be told apart.
_FRACTIONAL_CPU_LIMIT = 1.5

# A responsive daemon answers at once; a build may pull a base image and install into
# it; a probe run is a few file reads. Bounded so a stall fails rather than hangs.
_DAEMON_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 600
_RUN_TIMEOUT_SECONDS = 120

# The image is kept under a fixed tag, so later runs reuse its layers instead of reinstalling.
_PROBE_IMAGE_TAG = "infrahub-cgroup-probe:test"
_PROBE_DIR = "/probe"

# The module is imported on its own rather than through the ``infrahub`` package, whose
# import needs distribution metadata that a bare image lacks.
_PROBE = """\
import json, os
import psutil, resources
reading = resources.ProcessResources(machine=resources.PsutilMachine()).read()
print(json.dumps(reading.model_dump() | {
    "host_memory_total": psutil.virtual_memory().total,
    "host_processor_available": psutil.cpu_count(logical=True),
    "affinity_available": len(psutil.Process().cpu_affinity()),
    "pid_namespace_number": os.stat("/proc/self/ns/pid").st_ino,
}))
"""

# Every probe container gets this hostname, so the hostname part of the container name is known.
_PROBE_HOSTNAME = "telemetry-probe"


def _ancestor_limit_setup(cpus: int, memory_bytes: int) -> str:
    """Shell commands that put the limits on the process's parent group and move the process into an unlimited child.

    That is the shape a pod-level limit produces. The parent must be vacated before
    its controllers can be delegated to children.

    The commands run privileged against the host's cgroup hierarchy, so they refuse
    to act unless they have resolved the process's own non-root group: an unresolved
    path would place the limits on the root and throttle everything else sharing the
    machine.
    """
    return f"""
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
echo {memory_bytes} > $cgroup/memory.max
echo '{cpus * _CPU_PERIOD_US} {_CPU_PERIOD_US}' > $cgroup/cpu.max
"""


@dataclass(frozen=True)
class KernelCase:
    name: str

    container_options: dict[str, Any]
    """Docker options that put the container in the layout under test."""

    expected_assigned: int | None
    expected_memory_total: int | None
    """Bytes, or ``None`` when the reading should fall back to the whole host."""

    expected_usable: int | None = None
    """Cores the quota lets the process occupy, when a fractional quota makes that differ."""

    expected_affinity: int | None = None
    """The exact number of CPUs a ``cpuset`` restriction pins the process to.

    Every case caps the expected usable CPUs by the pinned CPUs the probe reports;
    this field only adds a check of that count.
    """

    setup: str = ""
    """Shell commands run in the container before the probe, in the probe's own process."""


KERNEL_CASES = [
    KernelCase(
        name="private_namespace_reads_container_limits",
        container_options={
            "cgroupns": "private",
            "nano_cpus": int(_FRACTIONAL_CPU_LIMIT * _NANO_CPUS_PER_CPU),
            "mem_limit": _MEMORY_LIMIT,
        },
        expected_assigned=2,
        expected_usable=1,
        expected_memory_total=_MEMORY_LIMIT,
    ),
    KernelCase(
        name="host_namespace_reads_container_limits",
        container_options={
            "cgroupns": "host",
            "nano_cpus": int(_FRACTIONAL_CPU_LIMIT * _NANO_CPUS_PER_CPU),
            "mem_limit": _MEMORY_LIMIT,
        },
        expected_assigned=2,
        expected_usable=1,
        expected_memory_total=_MEMORY_LIMIT,
    ),
    KernelCase(
        name="ancestor_limit_applies_to_an_unlimited_leaf",
        container_options={"cgroupns": "host", "privileged": True},
        expected_assigned=_WHOLE_CPU_LIMIT,
        expected_memory_total=_MEMORY_LIMIT,
        setup=_ancestor_limit_setup(cpus=_WHOLE_CPU_LIMIT, memory_bytes=_MEMORY_LIMIT),
    ),
    KernelCase(
        name="cpuset_without_quota_caps_available_by_affinity",
        container_options={"cpuset_cpus": "0-1"},
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
    try:
        docker = DockerClient(timeout=_DAEMON_TIMEOUT_SECONDS).client
        try:
            return str(docker.info().get("CgroupVersion")) == "2"
        finally:
            docker.close()
    except (DockerException, RequestException):
        return False


pytestmark = pytest.mark.skipif(
    not _docker_on_cgroup_v2(), reason="requires a running Docker daemon on a cgroup v2 host"
)


def _probe_dockerfile() -> str:
    """A Dockerfile on this interpreter's Python with the project's locked versions of the reader's dependencies."""
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
    packages = " ".join(f"{package}=={importlib.metadata.version(package)}" for package in ("psutil", "pydantic"))
    return (
        f"FROM python:{python}-slim\n"
        f"RUN pip install --no-cache-dir {packages}\n"
        f"COPY resources.py probe.py {_PROBE_DIR}/\n"
        f"WORKDIR {_PROBE_DIR}\n"
    )


@pytest.fixture(scope="module")
def probe_image(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Build a minimal image carrying the reader and only its runtime dependencies."""
    context = tmp_path_factory.mktemp("cgroup-probe")
    (context / "Dockerfile").write_text(_probe_dockerfile(), encoding="utf-8")
    (context / "probe.py").write_text(_PROBE, encoding="utf-8")
    shutil.copyfile(RESOURCES_MODULE, context / "resources.py")

    image = DockerImage(
        path=context,
        tag=_PROBE_IMAGE_TAG,
        clean_up=False,
        docker_client_kw={"timeout": _BUILD_TIMEOUT_SECONDS},
    )
    try:
        image.build()
    except (BuildError, APIError, RequestException) as exc:
        # The build pulls a base image and installs into it, so a runner without
        # registry access cannot produce the probe. That is a missing prerequisite
        # rather than a regression in the reader.
        pytest.skip(f"probe image could not be built: {str(exc)[-300:]}")
    return str(image)


def _run_probe(image: str, case: KernelCase) -> dict[str, Any]:
    """Run the probe in a container laid out as ``case`` describes and return the reading it prints.

    Raises:
        APIError: The daemon refused to start the container for a reason other than its CPU set.

    """
    # The setup must run in the probe's own process, since it moves that process into a child group.
    script = f"set -e\n{case.setup}\nexec python probe.py"
    container = (
        DockerContainer(image, docker_client_kw={"timeout": _RUN_TIMEOUT_SECONDS})
        .with_command(["sh", "-c", script])
        .with_kwargs(hostname=_PROBE_HOSTNAME, **case.container_options)
    )
    try:
        try:
            container.start()
        except APIError as exc:
            if "cpuset" not in str(exc).lower():
                raise
            # The case pins specific CPU ids, which a daemon confined to a different set
            # refuses before the reader ever runs.
            pytest.skip(f"the daemon does not allow this CPU set: {str(exc)[-200:]}")
        exit_status = container.get_wrapped_container().wait(timeout=_RUN_TIMEOUT_SECONDS)
        stdout, stderr = container.get_logs()
    finally:
        container.stop()

    assert exit_status["StatusCode"] == 0, f"container failed: {stderr.decode(errors='replace')}"
    return json.loads(stdout.decode().strip().splitlines()[-1])


@pytest.mark.parametrize("case", KERNEL_CASES, ids=[case.name for case in KERNEL_CASES])
def test_reader_against_real_cgroups(case: KernelCase, probe_image: str) -> None:
    reading = _run_probe(probe_image, case)

    assert reading["host"] == f"{_PROBE_HOSTNAME}/pid:[{reading['pid_namespace_number']}]"

    if case.expected_affinity is not None:
        assert reading["affinity_available"] == case.expected_affinity

    # 'available' is what the process can use: the host's count capped by the quota (rounded
    # down, since a fraction of a core cannot keep a whole one busy) and by the CPUs the
    # process may run on, which a daemon can restrict for every container it starts, while
    # 'assigned' rounds the same quota up to the cap that is enforced.
    quota_cap = case.expected_usable if case.expected_usable is not None else case.expected_assigned
    caps = [reading["host_processor_available"], reading["affinity_available"]]
    if quota_cap is not None:
        caps.append(quota_cap)
    assert reading["processor_available"] == min(caps)
    assert reading["processor_available"] >= 1

    assert reading["processor_assigned"] == case.expected_assigned
    assert reading["memory_available"] is not None
    if case.expected_memory_total is None:
        assert reading["memory_total"] == reading["host_memory_total"]
        assert reading["memory_available"] >= 0
    else:
        assert reading["memory_total"] == case.expected_memory_total
        assert 0 <= reading["memory_available"] <= case.expected_memory_total

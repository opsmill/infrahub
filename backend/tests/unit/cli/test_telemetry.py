"""Unit tests for the ``telemetry probe-resources`` CLI command's rendering.

``ProcessResources.diagnose()`` reads real host and cgroup state, so these
tests construct a fixed ``ResourceDiagnostics`` value instead and exercise the
two output branches directly: the rich-table render and the JSON serialization.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

import pytest
from rich.console import Console

from infrahub.cli.telemetry import _render, _to_json
from infrahub.telemetry.resources import CgroupLevel, ResourceDiagnostics, WorkerResourceReading
from tests.helpers.cli import remove_ansi_color


@dataclass
class RenderCase:
    name: str
    diagnostics: ResourceDiagnostics
    expected_present: list[str]
    expected_absent: list[str]


LIMITED_DIAGNOSTICS = ResourceDiagnostics(
    reading=WorkerResourceReading(
        host="worker-a",
        processor_available=2,
        processor_assigned=2,
        memory_total=536870912,
        memory_available=268435456,
    ),
    proc_cgroup="0::/docker/abc123",
    cgroup_v2_root=True,
    cgroup_v1_root=False,
    memory_limit=536870912,
    levels=[
        CgroupLevel(path="/sys/fs/cgroup", files={"cpu.max": "200000 100000", "memory.max": "536870912"}),
    ],
    host_processor_available=8,
    host_memory_total=17179869184,
)

UNLIMITED_DIAGNOSTICS = ResourceDiagnostics(
    reading=WorkerResourceReading(
        host="worker-b",
        processor_available=8,
        processor_assigned=None,
        memory_total=17179869184,
        memory_available=8589934592,
    ),
    proc_cgroup=None,
    cgroup_v2_root=False,
    cgroup_v1_root=False,
    memory_limit=None,
    levels=[
        CgroupLevel(path="/sys/fs/cgroup", files={}),
    ],
    host_processor_available=8,
    host_memory_total=17179869184,
)

RENDER_CASES = [
    RenderCase(
        name="cpu_and_memory_limits_enforced",
        diagnostics=LIMITED_DIAGNOSTICS,
        expected_present=[
            "processor_available",
            "2",
            "processor_assigned",
            "memory_total",
            "536870912 (0.50 GiB)",
            "memory_available",
            "268435456 (0.25 GiB)",
            "worker-a",
            "/sys/fs/cgroup",
            "cpu.max=200000 100000",
            "memory.max=536870912",
        ],
        expected_absent=[
            "no confirmed CPU limit",
            "no confirmed memory limit",
            "null (unbounded / unknown)",
        ],
    ),
    RenderCase(
        name="no_limits_enforced",
        diagnostics=UNLIMITED_DIAGNOSTICS,
        expected_present=[
            "processor_available",
            "8",
            "null (unbounded / unknown)",
            "17179869184 (16.00 GiB)",
            "8589934592 (8.00 GiB)",
            "worker-b",
            "processor_available reflects no confirmed CPU limit",
            "memory_total reflects no confirmed memory limit",
            "unreadable",
        ],
        expected_absent=[],
    ),
]


@pytest.mark.parametrize("case", RENDER_CASES, ids=[case.name for case in RENDER_CASES])
def test_render_table_output(case: RenderCase) -> None:
    buffer = io.StringIO()
    console = Console(file=buffer, width=200)

    _render(diagnostics=case.diagnostics, console=console)

    output = remove_ansi_color(buffer.getvalue())
    for expected in case.expected_present:
        assert expected in output
    for unexpected in case.expected_absent:
        assert unexpected not in output


def test_to_json_with_limits_enforced_serializes_reading_and_evidence() -> None:
    output = _to_json(LIMITED_DIAGNOSTICS)

    payload = json.loads(output)

    assert payload["reading"] == {
        "host": "worker-a",
        "processor_available": 2,
        "processor_assigned": 2,
        "memory_total": 536870912,
        "memory_available": 268435456,
    }
    assert payload["proc_cgroup"] == "0::/docker/abc123"
    assert payload["cgroup_v2_root"] is True
    assert payload["cgroup_v1_root"] is False
    assert payload["memory_limit"] == 536870912
    assert payload["host_processor_available"] == 8
    assert payload["host_memory_total"] == 17179869184
    assert payload["levels"] == [
        {"path": "/sys/fs/cgroup", "files": {"cpu.max": "200000 100000", "memory.max": "536870912"}}
    ]


def test_to_json_with_no_limits_enforced_serializes_null_fields() -> None:
    output = _to_json(UNLIMITED_DIAGNOSTICS)

    payload = json.loads(output)

    assert payload["reading"]["processor_assigned"] is None
    assert payload["proc_cgroup"] is None
    assert payload["memory_limit"] is None
    assert payload["levels"] == [{"path": "/sys/fs/cgroup", "files": {}}]

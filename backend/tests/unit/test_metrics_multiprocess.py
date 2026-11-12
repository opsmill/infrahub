from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from prometheus_client import Gauge

import infrahub
from infrahub import worker
from infrahub.api.admission import metrics as admission_metrics
from infrahub.database import metrics as database_metrics
from infrahub.workers import metrics as task_worker_metrics

if TYPE_CHECKING:
    from types import ModuleType

# A gauge without an explicit mode defaults to "all", which keeps the last value of a stopped process.
DEFAULT_MODE = "all"

GAUGE_MODULES: list[ModuleType] = [admission_metrics, database_metrics, task_worker_metrics, worker]

GAUGE_DEFINITION = re.compile(r"\bGauge\(")


def _gauges(module: ModuleType) -> dict[str, Gauge]:
    return {name: value for name, value in vars(module).items() if isinstance(value, Gauge)}


def test_every_module_defining_a_gauge_is_checked() -> None:
    source_root = Path(infrahub.__file__).parent
    defining_modules = {
        str(path.relative_to(source_root.parent))
        for path in source_root.rglob("*.py")
        if GAUGE_DEFINITION.search(path.read_text(encoding="utf-8"))
    }

    checked_modules = set()
    for module in GAUGE_MODULES:
        assert module.__file__ is not None
        checked_modules.add(str(Path(module.__file__).relative_to(source_root.parent)))

    assert defining_modules == checked_modules


@pytest.mark.parametrize("module", [pytest.param(module, id=module.__name__) for module in GAUGE_MODULES])
def test_every_gauge_declares_how_processes_are_combined(module: ModuleType) -> None:
    gauges = _gauges(module)

    assert gauges, f"{module.__name__} defines no gauge"
    assert {
        name: gauge._multiprocess_mode for name, gauge in gauges.items() if gauge._multiprocess_mode == DEFAULT_MODE
    } == {}

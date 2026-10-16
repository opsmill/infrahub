from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

DASHBOARD_DIR = Path(__file__).resolve().parents[3] / "development" / "grafana" / "provisioning" / "dashboards"
DASHBOARD_FILES = sorted(DASHBOARD_DIR.glob("*.json"))

DEPLOYMENT_LABEL_MATCHER = re.compile(
    r"""\b(?P<label>job|instance|container)\s*(?:=~|!~|!=|=)\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)')"""
)
MISLEADING_ADMISSION_TITLES = {"In-Flight vs Pool Capacity", "Slot Pool Saturation"}
# A panel that treats these limits as the highest bucket hides the longer durations recorded above them.
FORMER_HIGHEST_BUCKETS = {
    "infrahub_db_query_execution_seconds": "1",
    "infrahub_request_duration_seconds": "0.5",
}
BUCKET_MATCHER = re.compile(
    r"""\b(?P<metric>infrahub_db_query_execution_seconds|infrahub_request_duration_seconds)_bucket\s*\{[^}]*\ble\s*=\s*["'](?P<le>[^"']*)["']"""
)


def _panels(panels: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for panel in panels:
        yield panel
        yield from _panels(panel.get("panels", []))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _panel_queries(dashboard: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for panel in _panels(dashboard.get("panels", [])):
        for target in panel.get("targets", []):
            expr = target.get("expr")
            if isinstance(expr, str):
                yield str(panel.get("title")), expr


def test_dashboards_are_found() -> None:
    assert len(DASHBOARD_FILES) >= 7


@pytest.mark.parametrize("path", [pytest.param(path, id=path.name) for path in DASHBOARD_FILES])
def test_panel_queries_select_deployment_labels_through_variables(path: Path) -> None:
    fixed_matchers = [
        f"{title}: {match.group(0)}"
        for title, expr in _panel_queries(_load(path))
        for match in DEPLOYMENT_LABEL_MATCHER.finditer(expr)
        if (value := match.group("double") or match.group("single") or "") and "$" not in value
    ]

    assert fixed_matchers == []


@pytest.mark.parametrize("path", [pytest.param(path, id=path.name) for path in DASHBOARD_FILES])
def test_admission_panels_are_not_named_after_a_connection_pool(path: Path) -> None:
    titles = {panel.get("title") for panel in _panels(_load(path).get("panels", []))}

    assert titles & MISLEADING_ADMISSION_TITLES == set()


@pytest.mark.parametrize("path", [pytest.param(path, id=path.name) for path in DASHBOARD_FILES])
def test_panel_ids_are_unique(path: Path) -> None:
    ids = [panel["id"] for panel in _panels(_load(path).get("panels", [])) if "id" in panel]

    assert sorted(panel_id for panel_id in set(ids) if ids.count(panel_id) > 1) == []


@pytest.mark.parametrize("path", [pytest.param(path, id=path.name) for path in DASHBOARD_FILES])
def test_duration_panels_do_not_read_a_former_highest_bucket(path: Path) -> None:
    former_highest_buckets = [
        f"{title}: {match.group(0)}"
        for title, expr in _panel_queries(_load(path))
        for match in BUCKET_MATCHER.finditer(expr)
        if FORMER_HIGHEST_BUCKETS[match.group("metric")] == match.group("le")
    ]

    assert former_highest_buckets == []

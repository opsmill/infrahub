from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

DATASOURCE_FILE = (
    Path(__file__).resolve().parents[3] / "development" / "grafana" / "provisioning" / "datasources" / "datasource.yml"
)
TRACE_ID = "0af7651916cd43dd8448eb211c80319c"


def _datasource(datasource_type: str) -> dict[str, Any]:
    datasources = yaml.safe_load(DATASOURCE_FILE.read_text(encoding="utf-8"))["datasources"]
    (datasource,) = [datasource for datasource in datasources if datasource["type"] == datasource_type]
    return datasource


def _trace_id_matcher() -> re.Pattern[str]:
    derived_fields = _datasource("loki")["jsonData"]["derivedFields"]
    (field,) = [field for field in derived_fields if field["name"] == "trace_id"]
    return re.compile(field["matcherRegex"])


@dataclass
class TraceIdLineTestCase:
    name: str
    log_line: str


TRACE_ID_LINE_TEST_CASES: list[TraceIdLineTestCase] = [
    TraceIdLineTestCase(name="text_line", log_line=f"event='request done' trace_id={TRACE_ID} worker=1"),
    TraceIdLineTestCase(name="json_line", log_line=f'{{"event": "request done", "trace_id": "{TRACE_ID}"}}'),
    TraceIdLineTestCase(name="text_line_with_0x", log_line=f"trace_id=0x{TRACE_ID}"),
    # The log pipeline of the observability stack rewrites JSON lines of the API server into this form.
    TraceIdLineTestCase(
        name="line_rewritten_by_the_log_pipeline",
        log_line=f"2026-10-21T10:00:00Z server [info] request done RequestID=abc TraceID={TRACE_ID} ",
    ),
    TraceIdLineTestCase(name="json_line_with_0x", log_line=f'{{"trace_id": "0x{TRACE_ID}"}}'),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TRACE_ID_LINE_TEST_CASES])
def test_loki_links_each_trace_id_form_to_its_trace(test_case: TraceIdLineTestCase) -> None:
    match = _trace_id_matcher().search(test_case.log_line)

    assert match is not None
    assert match.group(1) == TRACE_ID


def test_loki_has_no_request_id_link() -> None:
    derived_fields = _datasource("loki")["jsonData"]["derivedFields"]

    assert [field["name"] for field in derived_fields] == ["trace_id"]


def test_tempo_finds_the_log_lines_of_a_trace_in_any_loki() -> None:
    traces_to_logs = _datasource("tempo")["jsonData"]["tracesToLogsV2"]

    assert traces_to_logs["spanStartTimeShift"] == "-1h"
    assert traces_to_logs["spanEndTimeShift"] == "1h"
    assert traces_to_logs["filterByTraceID"] is True
    assert traces_to_logs["customQuery"] is True
    # Provisioning reads `$$` as a literal `$`, so Grafana receives `${__trace.traceId}`.
    assert traces_to_logs["query"] == '{job=~".+"} |= "$${__trace.traceId}"'


@pytest.mark.parametrize("setting", ["tracesToMetrics", "traceQuery"])
def test_tempo_time_window_surrounds_the_span(setting: str) -> None:
    window = _datasource("tempo")["jsonData"][setting]

    assert window["spanStartTimeShift"] == "-1h"
    assert window["spanEndTimeShift"] == "1h"

# Manual checks: SDK layer 1, IFC-3419 (traceparent header)

- **Repository:** `opsmill/infrahub-sdk-python`, in the `python_sdk/` submodule
- **Branch:** `dp-20261015-trace-context-ifc-3419`
- **Base:** `infrahub-develop`
- **Head at the checks:** `0a98399` ("feat(client): send the W3C traceparent header when OpenTelemetry is installed
  [IFC-3419]")
- **Uncommitted changes at start:** none
- **Started:** 2026-10-19
- **Environment:** local Infrahub stack with the observability services (Tempo on port 3200), Infrahub
  virtual environment that imports the SDK from `python_sdk/`

## Checks

| # | Check | What changed | Source | Outcome |
|---|-------|--------------|--------|---------|
| 1 | An SDK call inside a span joins the caller's trace | Header in `_merge_request_headers`, `infrahub_sdk/trace_context.py` | Story 1 scenario 8; FR-001; T021 | pass |
| 2 | Without OpenTelemetry, the SDK works as before and sends no header | Import inside a function | Story 1 scenario 8; FR-001; T020, T021 | pass |
| 3 | The `tracing` extra installs the OpenTelemetry API, and a plain install does not | `pyproject.toml`, `uv.lock` | FR-001 | pass |
| 4 | The install guide describes the `tracing` extra | `docs/docs/python-sdk/guides/installation.mdx` | T022 | pass |
| 5 | Automated tests and linters | `tests/unit/sdk/test_trace_context.py`, `tests/unit/test_packaging_metadata.py` | T020, T022 | pass |

### Not covered by this layer

- Story 1 scenarios 1 and 3 (a flow run and its SDK calls in one trace) need the flow run span of
  IFC-3426 (layer 4).

### Known limits of this environment

- 8 tests in `tests/unit/pytest_plugin/test_plugin.py` fail on this Mac with or without the change: the
  `pytest-infrahub-performance-test` plugin of `infrahub-testcontainers` calls `psutil.cpu_freq()`, which
  fails here. The unit tests run with `-p no:pytest-infrahub-performance-test`.
- vale is not installed locally; CI runs it.

## Results

### Check 1: pass

`sdk_traceparent_check.py` (a span with a new trace ID around `InfrahubClient.get_version()`) printed
trace ID `fcbe292b731690bbf4ab0a9715dd8e20`; in Grafana Explore, Tempo, that trace contains the Infrahub
server spans (`Query.execute`, `execute_db_query_with_metadata`).

### Check 2: pass

`uv run --isolated --no-project --with ./python_sdk python sdk_without_otel_check.py` (an environment
with the SDK and its required packages only): "OpenTelemetry installed: False", "Trace context headers:
{}", and `get_version()` returned the Infrahub version with no error.

### Check 3: pass

`uv run --isolated --no-project --with './python_sdk[tracing]' …` printed `opentelemetry-api 1.45.1`;
check 2 showed that a plain install has no OpenTelemetry.

### Check 4: pass

The `### tracing` section of the install guide has the same layout as the other extras and says what
the extra installs, when the header is sent, and that an application with OpenTelemetry does not need it.

### Check 5: pass

- New tests and packaging tests: 40 passed, 2 skipped.
- Full unit suite with `-n 8`: 2351 passed; 11 failed, none caused by this change:
  - the 8 known `tests/unit/pytest_plugin/test_plugin.py` failures (see "Known limits");
  - 3 tests in `tests/unit/ctl/test_marketplace_app.py`: run in a real terminal, Rich adds bold codes
    (`\x1b[1m`) to version numbers, which the expected text does not have (`NO_COLOR=1` turns off colour,
    not bold). In a terminal emulated with `script`, the file fails the same way on this branch and on
    `infrahub-develop` (29 failed each); run without a terminal, it passes.
- `uv run invoke lint-code`: ruff, ty and mypy report no issues.

## Final report

- All 5 checks passed.
- Observed, not caused by this change: `tests/unit/ctl/test_marketplace_app.py` fails when run in a real
  terminal.
- Pull request: [opsmill/infrahub-sdk-python#1434](https://github.com/opsmill/infrahub-sdk-python/pull/1434),
  rebased on `infrahub-develop` (`89d078a6`).
- After the checks, `1e63596d` raised the minimum to `opentelemetry-api>=1.33` and made an invalid
  `OTEL_PROPAGATORS` send no header with one warning, after Patrick Ogenstad's review in Slack. It
  changes no behavior that checks 1 to 4 tested; its unit tests pass (42 passed, 2 skipped).
- After Patrick Ogenstad's review on the pull request, `79997aa6` added the version check: below
  `opentelemetry-api` 1.33 the SDK never imports OpenTelemetry. The pull request merged on
  2026-10-21 (merge commit `a7931235`).

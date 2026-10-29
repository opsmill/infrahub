# Manual checks: SDK layer 2, IFC-3420 (`infrahubctl` commands for the sampling ratio)

- **Repository:** `opsmill/infrahub-sdk-python`, in the `python_sdk/` submodule
- **Branch:** `dp-20261015-trace-sample-ratio-command-ifc-3420`
- **Base:** `infrahub-develop` (`8e4a4554`)
- **Head:** `51398c3d` ("feat(ctl): add infrahubctl commands for the temporary trace sampling ratio
  [IFC-3420]")
- **Uncommitted changes at start:** none
- **Started:** 2026-10-22
- **Environment:** local Infrahub stack built from Infrahub `develop` (`3f438ca96`, which contains the
  `/api/troubleshooting/trace-sample-ratio` endpoints), `infrahubctl` from the Infrahub virtual
  environment, which imports the SDK from `python_sdk/`

## Checks

| # | Check | What changed | Source | Outcome |
|---|-------|--------------|--------|---------|
| 1 | `get` shows the sampling ratio state | `get` command, `GET` | FR-026, FR-028; T080, T081 | pass |
| 2 | `set` sets a temporary ratio on every process | `set` command, client `_put` | Story 6 scenarios; FR-026, FR-027, FR-035; T080, T081 | pass |
| 3 | `clear` returns every process to the default ratio | `clear` command, client `_delete` | FR-026, FR-027; T080, T081 | pass |
| 4 | `set` rejects values outside the limits without a request | `--ratio` 0 to 1, `--duration` 1 to 86400 | FR-026; T080 | pass |
| 5 | With tracing off, the server's error is printed unchanged | Error output | FR-031; T080 | pass |
| 6 | Automated tests and linters | `test_troubleshooting_app.py`, `test_client_put_delete.py` | T080, T083 | pass |

## Results

### Check 1: pass

`uv run infrahubctl troubleshooting trace-sample-ratio get` with `INFRAHUB_ADDRESS` and
`INFRAHUB_API_TOKEN` set: table with "Tracing enabled: True", "Default ratio: 0.1", no temporary ratio,
"Ratio in force: 0.1". Without the token, the server's 403 message "You do not have the following
permission: global:super_admin:allow_all" was printed unchanged.

### Check 2: pass

`set --ratio 1 --duration 300` and `get` printed "Temporary ratio: 1.0", "Ratio in force: 1.0", default
0.1, and an end time 5 minutes after the request. After the second `set` (09:41:00), Loki had "Set the
temporary trace sampling ratio" from `infrahub-server-1` (4, one per API worker), `infrahub-task-worker-1`
and `infrahub-task-worker-2`.

Observed in the first run, not caused by this change:

- `infrahub-task-worker-2` logged nothing from about 09:37:30 to 09:40:47. RabbitMQ closed its
  connection at 09:38:33 ("missed heartbeats from client, timeout: 60s"), so it missed the first `set`
  (09:38:28) and had no `worker-events` queue. On `docker restart` (09:40:47) the old process woke up,
  logged the first change and "Reconnected to RabbitMQ", and its flow runs crashed on the termination
  signal. Cause not found; the tracer exports from a background thread (`BatchSpanProcessor`).
- Tempo was not running, so the workers logged "errors resolving infrahub-tempo:4317". Not a bug: Tempo
  is in the Compose profile `trace`, which `tasks/shared.py` adds only with `INFRAHUB_DEBUG_TRACE=true`;
  the setup set the `INFRAHUB_TRACE_*` variables by hand instead. `INFRAHUB_DEBUG_TRACE` is not
  documented in `dev/`, `docs/` or the `AGENTS.md` files.

### Check 3: pass

`clear` printed no temporary ratio and no end time, with "Ratio in force: 0.1". Loki had "Cleared the
temporary trace sampling ratio" from `infrahub-server-1` (4), `infrahub-task-worker-1` (1) and
`infrahub-task-worker-2` (1).

### Check 4: pass

`set --ratio 1.5 --duration 60` and `set --ratio 0.5 --duration 86401` were rejected by Typer with the
option and its range, and printed no table; `get` afterwards still showed no temporary ratio.

### Check 5: pass

Stack restarted without the tracing variables (`INFRAHUB_TRACE_ENABLE` false): `set` and `clear` each
printed "Tracing is not enabled on this instance; set INFRAHUB_TRACE_ENABLE" unchanged and exited with
code 1, with no table and no traceback; `get` showed "Tracing enabled: False".

### Check 6: pass

- New tests: 18 passed (10 command tests, 8 client tests).
- Full SDK unit suite without `INFRAHUB_ADDRESS` and `INFRAHUB_API_TOKEN`: 2936 passed; 11 failed, none
  in a file this branch changes:
  - 8 in `tests/unit/pytest_plugin/test_plugin.py`: the inner pytest loads the
    `pytest-infrahub-performance-test` plugin, whose `psutil.cpu_freq()` call fails on this Mac;
  - 3 in `tests/unit/ctl/test_marketplace_app.py`: in a real terminal, Rich adds bold codes to version
    numbers (seen on `infrahub-develop` too, see the IFC-3419 report).
- With `INFRAHUB_API_TOKEN` exported, `test_config.py::test_missing_password` fails and
  `test_cli.py::test_anonymous_info_detail_command_success` errors: `tests/conftest.py` removes
  `INFRAHUB_TOKEN` but not `INFRAHUB_API_TOKEN`. Both pass without it.
- `uv run invoke lint-code`: ruff, ty and mypy report no issues.

## Final report

- All 6 checks passed. Head `51398c3d`.
- Observed, not caused by this change. Daniel decided on 2026-10-22 to file items 1 and 2 as INBOX tickets
  and to keep items 3 to 5 in this report only:
  1. A task worker froze for about 3 minutes, lost its RabbitMQ connection and missed a broadcast
     (`infrahub`): [INBOX-390](https://opsmill.atlassian.net/browse/INBOX-390).
  2. `INFRAHUB_DEBUG_TRACE`, which starts Tempo with the dev stack, is not documented (`infrahub`):
     [INBOX-391](https://opsmill.atlassian.net/browse/INBOX-391).
  3. `tests/conftest.py` does not remove `INFRAHUB_API_TOKEN` (SDK).
  4. `pytest_plugin` tests fail on macOS because of `psutil.cpu_freq()` (`infrahub-testcontainers`).
  5. `test_marketplace_app.py` fails in a real terminal because of bold codes (SDK).
- Pull request: [opsmill/infrahub-sdk-python#1447](https://github.com/opsmill/infrahub-sdk-python/pull/1447),
  merged into `infrahub-develop` on 2026-10-27 (`6e206ec9`) after Pol Michel's review. The review commit
  `e13a9a0e` rejects a `nan` ratio and shortens the help texts and the changelog fragment.

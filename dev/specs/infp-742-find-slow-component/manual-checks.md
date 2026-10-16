# Manual checks: layer 1, IFC-3425 (masking of spans and logs)

- **Branch:** `dp-20261016-mask-telemetry-ifc-3425`
- **Base:** `dp-20261014-find-slow-component-infp-742` (the spec layer below)
- **Head:** `d6b221c72` ("fix(security): mask secrets and personal data in spans and logs [IFC-3425]")
- **Uncommitted changes at start:** none
- **Started:** 2026-10-16

## Checks

| # | Check | What changed | Source | Outcome |
|---|-------|--------------|--------|---------|
| 1 | Request spans hide the client IP address and the URL query string, and keep the path | `MaskingSpanExporter` in `backend/infrahub/trace.py`, rules in `backend/infrahub/masking.py` | Story 2 scenario 4; T012, T013 | pass |
| 2 | Database query spans keep the Cypher text and the query name readable | Same exporter; `query` and `query_name` match no rule | Story 2 scenario 5; T012, T013 | pass |
| 3 | The single sign-on token endpoint span has the path and no `code` or `state` | URL rule in `masking.py`, applied by the exporter | Story 2 scenario 2; T012, T013 | pass |
| 4 | A log line with a secret key or a URL with a query string reaches the log output masked | `mask_personal_data` and `LogMaskingFilter` in `backend/infrahub/log.py` | Story 2 scenarios 6 and 9; T014 | pass |
| 5 | Automated tests for what cannot be triggered by hand | Single sign-on spans and login log line, exception events, Prefect run logs | Story 2 scenarios 1, 3, 7, 8; T007 to T011 | pass |

### Spec scenarios without a manual check

Scenarios 1 and 3 (a real single sign-on login) need an identity provider, which the development stack
does not have. Scenario 7 (an exception event with a URL) and scenario 8 (flow run logs sent to the
Prefect server) cannot be triggered from outside. Check 5 runs the automated tests that cover them.

## Results

### Check 1: pass

Request `GET /api/schema/summary?branch=main&manual_check=secret123`, trace
`54ec382e07c5e30004710960a09fa527`. On the server span: `http.url` =
`http://localhost:8000/api/schema/summary?[MASKED]`, `http.target` and `http.route` =
`/api/schema/summary`, `net.peer.ip` = `[MASKED]`; `secret123` in no attribute. Daniel first looked at a
child span ("http send"), which has no URL attributes; on the parent span the result matched.

### Check 2: pass

Same trace. The three `execute_db_query_with_metadata` spans show the full Cypher text in `query`, the
query names `account_token_validate`, `node_list_get_info` and `node_list_get_attribute`, and `rows`.

### Check 3: pass

With a fake OIDC provider `provider1` (discovery URL on `.invalid`), `GET
/api/oidc/provider1/token?code=manualcode123&state=manualstate456` returned 400 "Invalid 'state'
parameter". Trace `37bb44745deb819ea1848611ed062703`: `http.url` ends with `?[MASKED]`, the path is in
`http.route`, and the code and the state appear in no attribute or event.

### Check 4: pass

`configure_logging(production=True)` in the server container, then three lines: `api_token` and
`email` read `[MASKED]` and `account_id` stays readable; a structlog message and a `prefect.flow_runs`
message both show the URL with `?[MASKED]`. None of the secret values appears.

### Check 5: pass

`uv run pytest backend/tests/unit/test_masking.py backend/tests/unit/test_trace.py
backend/tests/unit/test_log.py backend/tests/unit/workers -q`: 178 passed.
`uv run pytest backend/tests/component/api/test_sso_token_telemetry.py -q`: 2 passed.

## Summary

All 5 checks passed on 2026-10-16. No bug and no skipped check. Next step: open the draft pull
request of IFC-3425.

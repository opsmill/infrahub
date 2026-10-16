# Contract: Temporary Trace Sampling Ratio (REST)

**Requirements**: FR-026 to FR-031, FR-036 | **Status**: approved by Damien Garros on
2026-10-15 ([Slack](https://opsmillworkspace.slack.com/archives/C08075KCU3A/p1792057541808779?thread_ts=1792048837.114539&cid=C08075KCU3A))

Three public endpoints under a new troubleshooting router, `/api/troubleshooting` (FR-036). They are in
the OpenAPI schema (`schema/openapi.json`), with a summary and a description that says why the endpoint
exists: record more traces during an incident without a restart, because a restart can remove the slow
behaviour. Later troubleshooting endpoints go under the same prefix. All three require an
authenticated account with the global permission `super_admin` (`ALLOW_ALL`), as
`POST /api/response-delay` does; otherwise the request is rejected with the standard permission error
(FR-029).

The state returned is the state of the process that handled the request. Other processes apply a
change within seconds (FR-027).

## Response body: `TraceSampleRatioAPI`

| Field | Type | Value |
|-------|------|-------|
| `enabled` | bool | False when `INFRAHUB_TRACE_ENABLE` is false; all other fields are then empty. |
| `default_ratio` | float or null | `INFRAHUB_TRACE_SAMPLE_RATIO`. |
| `temporary_ratio` | float or null | The temporary ratio in force, or null. |
| `expires_at` | ISO 8601 UTC or null | When the temporary ratio stops applying, or null. |
| `ratio_in_force` | float or null | The ratio used for new traces now. |

## `GET /api/troubleshooting/trace-sample-ratio`

Returns `TraceSampleRatioAPI`. Works when tracing is off (`enabled: false`).

## `PUT /api/troubleshooting/trace-sample-ratio`

Request body `TraceSampleRatioUpdateAPI`:

| Field | Type | Rules |
|-------|------|-------|
| `ratio` | float | Required, 0 to 1 inclusive. |
| `duration_seconds` | int | Required, 1 to 86400 (24 hours). The end time is the time of the request plus this duration. |

Effects, in order:

1. Validates the body. A missing field or a value outside its range returns HTTP 422 with the
   validation error, which names the limit (FR-026). A duration replaces an end time in the request, so
   an end time in the past cannot be sent.
2. When tracing is off, returns HTTP 400 with the error "Tracing is not enabled on this instance; set
   `INFRAHUB_TRACE_ENABLE`" (`ProcessingError`, FR-031). Nothing is broadcast.
3. Broadcasts `RefreshSettingsTraceSampleRatio(ratio, expires_at)`. A new change replaces the active one.
4. Sends `TraceSampleRatioUpdatedEvent` (FR-030).
5. Returns `TraceSampleRatioAPI` with the new state.

## `DELETE /api/troubleshooting/trace-sample-ratio`

Clears the temporary ratio: broadcasts the message with empty `ratio` and `expires_at`, sends the event
with `cleared: true`, and returns the new state. Same error as `PUT` when tracing is off.

## Log line in each process (FR-035)

When a process applies the broadcast, it writes one log line: "Set the temporary trace sampling ratio"
with `ratio` and `expires_at`, or "Cleared the temporary trace sampling ratio". The operator searches
for these lines in their log store to check that every API server and task worker applied the change.

## `infrahubctl`

Tracked in [IFC-3420](https://opsmill.atlassian.net/browse/IFC-3420). A command in
[infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python) calls these
endpoints to read, set (ratio and duration) and clear the ratio, and prints the error message of
FR-031 unchanged. Its name and options are decided in that repository.

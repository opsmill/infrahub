# Data Model: Find the Slow Component of an Infrahub Instance

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Nothing in this feature is stored in the Neo4j database. The entities below live in settings, in the
memory of each process, on the message bus, in the event stream, or in the telemetry that leaves the
process. Metric names and labels are in [contracts/metrics.md](contracts/metrics.md).

## Default sampling ratio

A setting read once at process startup.

| Field | Type | Rules |
|-------|------|-------|
| `INFRAHUB_TRACE_SAMPLE_RATIO` (`TraceSettings.sample_ratio`) | float | 0 to 1 inclusive. Default 0.1, provisional until the cost measurement (SC-006). Read only when `INFRAHUB_TRACE_ENABLE` is true. |

## Sampler state (one per process)

Kept in memory by `infrahub.trace::RatioSampler`. Exposed as the frozen dataclass
`infrahub.trace::SampleRatioState`.

| Field | Type | Rules |
|-------|------|-------|
| `default_ratio` | float | From the setting above. Never changes while the process runs. |
| `temporary_ratio` | float or empty | Set by a ratio change message. Empty when none is in force. |
| `expires_at` | UTC datetime or empty | Set together with `temporary_ratio`. |
| `ratio_in_force` | float | `temporary_ratio` while the current time is before `expires_at`, else `default_ratio`. |

State transitions:

```text
default ──set(ratio, expires_at)──▶ temporary
temporary ──set(ratio, expires_at)──▶ temporary (the new values replace the old ones)
temporary ──clear──▶ default
temporary ──current time ≥ expires_at──▶ default (checked for each new trace; no timer)
any ──process restart──▶ default
```

A span whose caller sent a trace context follows the caller's decision, whatever the ratio in force
(FR-007).

## Ratio change message

`infrahub.message_bus.messages::RefreshSettingsTraceSampleRatio`, routing key
`refresh.settings.trace_sample_ratio`, broadcast to every process bound to `refresh.settings.*`.

| Field | Type | Rules |
|-------|------|-------|
| `ratio` | float or empty | 0 to 1. Empty means "clear". |
| `expires_at` | UTC datetime or empty | Set if and only if `ratio` is set. |

## Ratio change event

`infrahub.events.trace_action::TraceSampleRatioUpdatedEvent`, name
`infrahub.trace.sample_ratio_updated`. One event per change, sent by the API process that handled the
request. The account is in the event metadata.

| Field | Type | Rules |
|-------|------|-------|
| `previous_ratio` | float | Ratio in force on the handling process before the change. |
| `new_ratio` | float | Ratio in force after the change; the default ratio after a clear. |
| `expires_at` | UTC datetime or empty | Empty after a clear. |
| `cleared` | bool | True when the administrator cleared the temporary ratio. |

A failure to send the event is logged and does not fail the request, because the change is already
applied.

## Masking rule

`infrahub.masking::MaskingRule`, used by spans and logs. Rules in `infrahub.masking::MASKING_RULES`;
the first rule that applies to a key wins.

| Rule | Keys | Masked result |
|------|------|---------------|
| Client IP address | `net.peer.ip`, `client.address`, `client_ip` | `[MASKED]` |
| URL | `http.url`, `http.target`, `url.full`, `url` | Path kept, query string replaced: `/path?[MASKED]` |
| Query string and account name | `url.query`, `account_name` | `[MASKED]` |
| Secrets and personal data | Any key that contains `token`, `password`, `secret`, `email`, `user_name` or `username`, in any case | `[MASKED]` |
| Log audit fields | Added when [INFP-745](https://opsmill.atlassian.net/browse/INFP-745) lists them | `[MASKED]` |

Cypher text (`db.statement` and the query attributes), URL paths and query names never match a rule.

## Task worker flow run

Not stored. Two values are read from the Prefect flow run when a task worker starts it:

| Field | Source | Use |
|-------|--------|-----|
| `flow` | Flow function name | Label of both task worker metrics. Never the run ID. |
| `queue` | `flow_run.work_queue_name` (`high`, `medium`, `low`) | Label of both metrics; `unknown` when empty. |
| Start delay | Start time minus `flow_run.expected_start_time`, at least 0 | Not recorded when the expected start time is empty. |
